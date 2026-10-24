import secrets
from datetime import timedelta

from pathlib import Path
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import IntegrityError
from django.db.models import Sum, F
from django.utils import timezone

from .forms import (
    RegisterForm,
    LoginForm,
    ForgotPasswordRequestForm,
    SetNewPasswordForm,
    EmailVerificationOTPForm,
    ProfileForm,
    AvatarUploadForm,
    UsernameChangeForm,
    EmailChangeRequestForm,
    EmailChangeConfirmForm,
)
from .models import (
    UserProfile,
    EmailVerificationCode,
    PasswordResetToken,
    PendingEmailChange,
    LoginLockout,
    AccountEvent,
)
from config.db_utils import atomic_immediate
from .emails import (
    send_verification_otp_email,
    send_verification_success_email,
    send_password_reset_email,
    send_password_reset_success_email,
    send_welcome_email,
)
from .services.avatar_service import process_and_save_avatar, remove_avatar
from .services.username_service import change_username, get_username_cooldown_status
from .services.email_change_service import (
    request_email_change,
    confirm_email_change,
    cancel_email_change,
)
from .services.otp_service import issue_otp
from .services.email_service import send_templated_email
from documents.models import Document
from sharing.models import SharePass
from audit.models import get_client_ip

User = get_user_model()


def landing_view(request):
    """Public landing page view."""
    return render(request, "pages/landing.html")


def register_view(request):
    """
    User registration view with auto-login on success, profile creation,
    and automatic email verification OTP & welcome dispatch.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Ensure profile exists
            profile, _ = UserProfile.objects.get_or_create(user=user)

            # Generate and dispatch initial email verification OTP
            if user.email:
                raw_otp = f"{secrets.randbelow(900000) + 100000}"
                expires_at = timezone.now() + timedelta(minutes=15)
                otp_record = EmailVerificationCode(
                    user=user,
                    email=user.email,
                    expires_at=expires_at,
                )
                otp_record.set_code(raw_otp)
                otp_record.save()

                send_verification_otp_email(user, raw_otp, expires_at)
                send_welcome_email(user)

            login(request, user)
            messages.success(request, f"Welcome to Passli, {user.username}! Your personal vault is ready.")
            return redirect("dashboard")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


LOGIN_MAX_FAILED_ATTEMPTS = 5


class CustomLoginView(LoginView):
    """
    Custom LoginView with database-backed per-username and per-IP exponential lockout.
    Enforces a 1-minute initial lockout after 5 consecutive failed attempts,
    doubling up to 24 hours on subsequent failures, returning HTTP 429 with Retry-After.
    """

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            username = request.POST.get("username", "").strip()[:150]
            client_ip = get_client_ip(request) or "127.0.0.1"
            if username:
                lockout = LoginLockout.objects.filter(username=username, ip_address=client_ip).first()
                if lockout and lockout.is_locked:
                    retry_after = lockout.retry_after_seconds
                    form = self.get_form()
                    response = self.render_to_response(
                        self.get_context_data(
                            form=form,
                            error_message=f"Too many failed login attempts for '{username}'. Access is temporarily locked. Please retry in {retry_after} seconds.",
                            retry_after=retry_after,
                        ),
                        status=429,
                    )
                    response["Retry-After"] = str(retry_after)
                    return response
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        username = self.request.POST.get("username", "").strip()[:150]
        client_ip = get_client_ip(self.request) or "127.0.0.1"
        if username:
            try:
                lockout, _ = LoginLockout.objects.get_or_create(
                    username=username, ip_address=client_ip, defaults={"failed_attempts": 0}
                )
            except IntegrityError:
                lockout = LoginLockout.objects.get(username=username, ip_address=client_ip)
            with atomic_immediate():
                lockout = LoginLockout.objects.select_for_update().get(id=lockout.id)
                lockout.failed_attempts = F("failed_attempts") + 1
                lockout.save(update_fields=["failed_attempts", "updated_at"])
                lockout.refresh_from_db(fields=["failed_attempts"])
                failures = lockout.failed_attempts

                if failures >= LOGIN_MAX_FAILED_ATTEMPTS:
                    power = failures - LOGIN_MAX_FAILED_ATTEMPTS
                    lockout_seconds = min(60 * (2**power), 86400)
                    lockout.locked_until = timezone.now() + timedelta(seconds=lockout_seconds)
                    lockout.save(update_fields=["locked_until", "updated_at"])
                    retry_after = lockout_seconds
                    response = self.render_to_response(
                        self.get_context_data(
                            form=form,
                            error_message=f"Too many failed login attempts ({failures}/{LOGIN_MAX_FAILED_ATTEMPTS}). Access is temporarily locked for {retry_after} seconds.",
                            retry_after=retry_after,
                        ),
                        status=429,
                    )
                    response["Retry-After"] = str(retry_after)
                    return response

        return super().form_invalid(form)

    def form_valid(self, form):
        username = form.cleaned_data.get("username", "").strip()[:150]
        client_ip = get_client_ip(self.request) or "127.0.0.1"
        if username:
            LoginLockout.objects.filter(username=username, ip_address=client_ip).update(
                failed_attempts=0, locked_until=None
            )
        messages.success(self.request, f"Welcome back, {form.get_user().username}!")
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("dashboard")


class CustomLogoutView(LogoutView):
    """Custom LogoutView redirecting to landing page with message."""

    next_page = reverse_lazy("landing")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, "You have been securely signed out.")
        return super().dispatch(request, *args, **kwargs)


@login_required(login_url="login")
def dashboard_view(request):
    """
    Authenticated user personal vault dashboard.
    Displays vault statistics, active share passes, storage usage, email verification status, and quick actions.
    """
    user_docs = Document.objects.filter(user=request.user)
    total_docs_count = user_docs.count()

    # Calculate storage
    total_bytes = user_docs.aggregate(total=Sum("file_size"))["total"] or 0
    storage_used_mb = total_bytes / (1024 * 1024)
    storage_quota_mb = 500.0  # 500 MB default vault quota
    storage_pct = min(100, int((storage_used_mb / storage_quota_mb) * 100)) if storage_quota_mb > 0 else 0

    # Share passes metrics
    all_passes = SharePass.objects.filter(owner=request.user).prefetch_related("documents").order_by("-created_at")
    total_passes_count = all_passes.count()
    active_passes = [p for p in all_passes if p.is_active()]
    active_passes_count = len(active_passes)
    recent_passes = active_passes[:4]

    recent_documents = user_docs.order_by("-created_at")[:4]

    # Email verification profile status
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    context = {
        "total_documents": total_docs_count,
        "total_passes": total_passes_count,
        "active_passes": active_passes_count,
        "storage_used_mb": f"{storage_used_mb:.1f}",
        "storage_quota_mb": f"{storage_quota_mb:.0f}",
        "storage_pct": storage_pct,
        "recent_documents": recent_documents,
        "recent_passes": recent_passes,
        "is_email_verified": profile.is_email_verified,
    }
    return render(request, "accounts/dashboard.html", context)


# ==============================================================================
# Password Recovery & Reset Views (OWASP & Anti-Enumeration Compliant)
# ==============================================================================


def password_reset_request_view(request):
    """
    Password reset initiation view.
    Always returns a generic success notification regardless of whether the account exists
    to strictly prevent account enumeration.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = ForgotPasswordRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            client_ip = get_client_ip(request)

            matched_users = User.objects.filter(email__iexact=email)
            for target_user in matched_users:
                # Rate-limit reset requests (max 1 new token per 60 seconds per user)
                recent_token = PasswordResetToken.objects.filter(
                    user=target_user, created_at__gt=timezone.now() - timedelta(seconds=60)
                ).exists()

                if not recent_token:
                    token_record, raw_token = PasswordResetToken.create_token_for_user(
                        user=target_user, ip_address=client_ip, ttl_minutes=30
                    )
                    send_password_reset_email(target_user, raw_token, token_record.expires_at)

            return render(request, "accounts/password_reset_done.html", {"submitted_email": email})
    else:
        form = ForgotPasswordRequestForm()

    return render(request, "accounts/password_reset_request.html", {"form": form})


def password_reset_confirm_view(request, token):
    """
    Validates single-use reset token and permits user to set a new master passphrase.
    Invalidates session and triggers a security confirmation email upon success.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    token_record = PasswordResetToken.get_valid_token(token)
    if not token_record:
        return render(request, "accounts/password_reset_invalid.html", status=400)

    user = token_record.user

    if request.method == "POST":
        form = SetNewPasswordForm(user, request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["password1"]
            user.set_password(new_password)
            user.save()

            # Mark token used immediately to prevent replay
            token_record.mark_used()

            # Invalidate all other reset tokens for this user
            PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

            # Send confirmation email
            send_password_reset_success_email(user, request=request)

            messages.success(
                request, "Your master passphrase has been successfully reset. Please sign in with your new credentials."
            )
            return redirect("login")
    else:
        form = SetNewPasswordForm(user)

    return render(
        request,
        "accounts/password_reset_confirm.html",
        {
            "form": form,
            "user_obj": user,
            "token": token,
        },
    )


# ==============================================================================
# Email Verification & OTP Views
# ==============================================================================


@login_required(login_url="login")
def verify_email_view(request):
    """
    Verifies user's email address via server-generated 6-digit OTP code.
    Enforces maximum attempts, expiration, and single-use invalidation.
    """
    if not request.user.email:
        messages.warning(request, "Please add an email address in account settings before verifying.")
        return redirect(reverse("account_settings") + "#email")

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.is_email_verified:
        messages.info(request, "Your email address is already verified.")
        return redirect("dashboard")

    # Look for active verification code scoped to verify_email purpose
    active_code = EmailVerificationCode.objects.filter(
        user=request.user,
        email=request.user.email,
        purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        is_used=False,
        expires_at__gt=timezone.now(),
    ).first()

    if request.method == "POST":
        form = EmailVerificationOTPForm(request.POST)
        if form.is_valid():
            submitted_code = form.cleaned_data["code"]

            if not active_code:
                messages.error(
                    request,
                    "No active verification code found or your code has expired. Please request a new code below.",
                )
            elif active_code.is_locked:
                messages.error(
                    request,
                    "Too many incorrect attempts on this code. For security, please request a new verification code.",
                )
            elif active_code.verify_code(submitted_code):
                profile.is_email_verified = True
                profile.save(update_fields=["is_email_verified", "updated_at"])

                send_verification_success_email(request.user)

                messages.success(
                    request, "Email verification complete! Your account security routing is now fully operational."
                )
                return redirect("dashboard")
            else:
                remaining = max(0, active_code.max_attempts - active_code.attempts)
                if remaining > 0:
                    messages.error(
                        request, f"Invalid verification code. {remaining} attempt(s) remaining before security lockout."
                    )
                else:
                    messages.error(
                        request, "Maximum verification attempts exceeded. Please request a new verification code."
                    )
    else:
        form = EmailVerificationOTPForm()

    return render(
        request,
        "accounts/verify_email.html",
        {
            "form": form,
            "has_active_code": bool(active_code and not active_code.is_locked),
            "user_email": request.user.email,
        },
    )


@login_required(login_url="login")
def resend_verification_otp_view(request):
    """
    Generates and dispatches a fresh 6-digit OTP code with strict 60-second cooldown protection.
    """
    if not request.user.email:
        messages.warning(
            request, "Please add an email address in account settings before requesting a verification code."
        )
        return redirect(reverse("account_settings") + "#email")

    if request.method != "POST":
        return redirect("verify_email")

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.is_email_verified:
        messages.info(request, "Your email address is already verified.")
        return redirect("dashboard")

    # Check 60-second cooldown for verify_email purpose
    recent_code = EmailVerificationCode.objects.filter(
        user=request.user,
        purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        created_at__gt=timezone.now() - timedelta(seconds=60),
    ).first()

    if recent_code:
        messages.warning(request, "Please wait a minute before requesting another verification code.")
        return redirect("verify_email")

    # Invalidate previous unused codes for verify_email purpose
    EmailVerificationCode.objects.filter(
        user=request.user,
        purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        is_used=False,
    ).update(is_used=True)

    # Generate fresh 6-digit code
    raw_otp = f"{secrets.randbelow(900000) + 100000}"
    expires_at = timezone.now() + timedelta(minutes=15)
    otp_record = EmailVerificationCode(
        user=request.user,
        email=request.user.email,
        purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        expires_at=expires_at,
    )
    otp_record.set_code(raw_otp)
    otp_record.save()

    send_verification_otp_email(request.user, raw_otp, expires_at)

    messages.success(request, f"A fresh verification code has been dispatched to {request.user.email}.")
    return redirect("verify_email")


# ==============================================================================
# Account Settings & Authenticated Avatar Views
# ==============================================================================


@login_required(login_url="login")
def account_settings_view(request):
    """
    Unified Account Settings interface for standard users and staff/administrators.
    Provides sectioned controls for Profile, Username, Email, Password, and Activity.
    Always transmits Cache-Control: no-store and enforces POST-only mutations with CSRF.
    """
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    cooldown_status = get_username_cooldown_status(user)

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        if action == "update_profile":
            profile_form = ProfileForm(request.POST)
            if profile_form.is_valid():
                profile.display_name = profile_form.cleaned_data["display_name"]
                profile.save(update_fields=["display_name", "updated_at"])
                messages.success(request, "Your profile details have been updated.")
                return redirect(reverse("account_settings") + "#profile")
            else:
                messages.error(request, "Could not update profile. Please correct the errors below.")

        elif action == "upload_avatar":
            avatar_form = AvatarUploadForm(request.POST, request.FILES)
            if avatar_form.is_valid():
                try:
                    process_and_save_avatar(user, request.FILES["avatar"], request=request)
                    messages.success(request, "Avatar updated successfully.")
                    return redirect(reverse("account_settings") + "#profile")
                except ValidationError as exc:
                    messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
                    return redirect(reverse("account_settings") + "#profile")
            else:
                messages.error(request, "Please choose a valid image file (JPEG, PNG, or WebP up to 2 MB).")
                return redirect(reverse("account_settings") + "#profile")

        elif action == "remove_avatar":
            remove_avatar(user, request=request)
            messages.success(request, "Avatar removed.")
            return redirect(reverse("account_settings") + "#profile")

        elif action == "change_username":
            username_form = UsernameChangeForm(user, request.POST)
            if username_form.is_valid():
                try:
                    change_username(
                        user=user,
                        new_username=username_form.cleaned_data["new_username"],
                        current_password=username_form.cleaned_data["current_password"],
                        request=request,
                    )
                    messages.success(request, f"Your username has been changed to '{user.username}'.")
                    return redirect(reverse("account_settings") + "#username")
                except ValidationError as exc:
                    messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
                    return redirect(reverse("account_settings") + "#username")
            else:
                err_msg = username_form.errors.get("new_username") or username_form.errors.get("current_password")
                if err_msg:
                    messages.error(request, err_msg[0])
                else:
                    messages.error(request, "Could not update username. Please review the form.")
                return redirect(reverse("account_settings") + "#username")

        elif action == "request_email_change":
            email_request_form = EmailChangeRequestForm(user, request.POST)
            if email_request_form.is_valid():
                try:
                    success, msg = request_email_change(
                        user=user,
                        new_email=email_request_form.cleaned_data["new_email"],
                        current_password=email_request_form.cleaned_data["current_password"],
                        request=request,
                    )
                    if success:
                        messages.success(request, msg)
                    else:
                        messages.error(request, msg)
                    return redirect(reverse("account_settings") + "#email")
                except ValidationError as exc:
                    messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
                    return redirect(reverse("account_settings") + "#email")
            else:
                err_msg = email_request_form.errors.get("new_email") or email_request_form.errors.get(
                    "current_password"
                )
                if err_msg:
                    messages.error(request, err_msg[0])
                else:
                    messages.error(request, "Could not process email change. Please review the form.")
                return redirect(reverse("account_settings") + "#email")

        elif action == "confirm_email_change":
            email_confirm_form = EmailChangeConfirmForm(request.POST)
            if email_confirm_form.is_valid():
                success, msg = confirm_email_change(
                    user=user,
                    submitted_code=email_confirm_form.cleaned_data["code"],
                    request=request,
                )
                if success:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
                return redirect(reverse("account_settings") + "#email")
            else:
                err_msg = email_confirm_form.errors.get("code")
                if err_msg:
                    messages.error(request, err_msg[0])
                else:
                    messages.error(request, "Please enter a valid 6-digit verification code.")
                return redirect(reverse("account_settings") + "#email")

        elif action == "resend_email_change_otp":
            pending = PendingEmailChange.objects.filter(user=user).first()
            if not pending:
                messages.error(request, "No pending email change request found.")
                return redirect(reverse("account_settings") + "#email")

            try:
                _, raw_otp = issue_otp(
                    user=user,
                    email=pending.new_email,
                    purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
                )
                send_templated_email(
                    subject="Passli Vault: Verify Your New Email Address",
                    template_base="email_change_otp",
                    context={
                        "username": user.username,
                        "new_email": pending.new_email,
                        "otp_code": raw_otp,
                        "ttl_minutes": 15,
                    },
                    recipient_list=[pending.new_email],
                    fail_silently=True,
                )
                messages.success(request, f"A fresh verification code has been dispatched to {pending.new_email}.")
            except ValidationError as exc:
                messages.warning(request, exc.message if hasattr(exc, "message") else str(exc))
            return redirect(reverse("account_settings") + "#email")

        elif action == "cancel_email_change":
            cancel_email_change(user, request=request)
            messages.info(request, "Pending email change request cancelled.")
            return redirect(reverse("account_settings") + "#email")

    # GET request form instances and context
    profile_form = ProfileForm(initial={"display_name": profile.display_name})
    avatar_form = AvatarUploadForm()
    username_form = UsernameChangeForm(user=user)
    email_request_form = EmailChangeRequestForm(user=user)
    email_confirm_form = EmailChangeConfirmForm()
    pending_email_change = PendingEmailChange.objects.filter(user=user).first()
    recent_activity = AccountEvent.objects.filter(user=user).order_by("-created_at")[:10]

    resend_cooldown_seconds = 0
    if pending_email_change:
        latest_code = (
            EmailVerificationCode.objects.filter(
                user=user,
                purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
            )
            .order_by("-created_at")
            .first()
        )
        if latest_code:
            elapsed = (timezone.now() - latest_code.created_at).total_seconds()
            if elapsed < 60:
                resend_cooldown_seconds = max(0, int(60 - elapsed))

    context = {
        "profile": profile,
        "profile_form": profile_form,
        "avatar_form": avatar_form,
        "username_form": username_form,
        "email_request_form": email_request_form,
        "email_confirm_form": email_confirm_form,
        "pending_email_change": pending_email_change,
        "resend_cooldown_seconds": resend_cooldown_seconds,
        "cooldown_status": cooldown_status,
        "recent_activity": recent_activity,
        "has_avatar": bool(profile.avatar_path),
        "avatar_url": reverse("avatar_serve_self") if profile.avatar_path else None,
    }

    response = render(request, "accounts/settings.html", context)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required(login_url="login")
def avatar_serve_view(request, user_id=None):
    """
    Authenticated delivery view for user avatars.
    Avatars are never served via public /media routes.
    Staff and superusers may view any user's avatar; standard users can only view their own.
    Sends X-Content-Type-Options: nosniff and Cache-Control: private.
    """
    if user_id is None:
        target_user = request.user
    else:
        target_user = get_object_or_404(User, pk=user_id)

    if target_user != request.user and not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Access denied.")

    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    if not profile.avatar_path:
        raise Http404("Avatar not configured.")

    clean_path = str(profile.avatar_path).lstrip("/\\").replace("\\", "/")
    media_root = Path(settings.MEDIA_ROOT).resolve()
    full_path = (media_root / clean_path).resolve()

    try:
        full_path.relative_to(media_root)
    except ValueError:
        raise Http404("Avatar path is invalid.")

    if not full_path.is_file():
        raise Http404("Avatar file not found on disk.")

    with open(full_path, "rb") as f:
        content = f.read()

    response = HttpResponse(content, content_type="image/webp")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
