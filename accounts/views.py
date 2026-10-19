import secrets
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Sum
from django.utils import timezone

from .forms import (
    RegisterForm,
    LoginForm,
    ForgotPasswordRequestForm,
    SetNewPasswordForm,
    EmailVerificationOTPForm,
)
from .models import UserProfile, EmailVerificationCode, PasswordResetToken
from .emails import (
    send_verification_otp_email,
    send_verification_success_email,
    send_password_reset_email,
    send_password_reset_success_email,
    send_welcome_email,
)
from documents.models import Document
from sharing.models import SharePass
from audit.models import get_client_ip

User = get_user_model()


def landing_view(request):
    """Public landing page view."""
    return render(request, 'pages/landing.html')


def register_view(request):
    """
    User registration view with auto-login on success, profile creation,
    and automatic email verification OTP & welcome dispatch.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
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
            return redirect('dashboard')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


class CustomLoginView(LoginView):
    """Custom LoginView with custom template and authentication form."""
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().username}!")
        return super().form_valid(form)

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy('dashboard')


class CustomLogoutView(LogoutView):
    """Custom LogoutView redirecting to landing page with message."""
    next_page = reverse_lazy('landing')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, "You have been securely signed out.")
        return super().dispatch(request, *args, **kwargs)


@login_required(login_url='login')
def dashboard_view(request):
    """
    Authenticated user personal vault dashboard.
    Displays vault statistics, active share passes, storage usage, email verification status, and quick actions.
    """
    user_docs = Document.objects.filter(user=request.user)
    total_docs_count = user_docs.count()

    # Calculate storage
    total_bytes = user_docs.aggregate(total=Sum('file_size'))['total'] or 0
    storage_used_mb = total_bytes / (1024 * 1024)
    storage_quota_mb = 500.0  # 500 MB default vault quota
    storage_pct = min(100, int((storage_used_mb / storage_quota_mb) * 100)) if storage_quota_mb > 0 else 0

    # Share passes metrics
    all_passes = SharePass.objects.filter(owner=request.user).prefetch_related('documents').order_by('-created_at')
    total_passes_count = all_passes.count()
    active_passes = [p for p in all_passes if p.is_active()]
    active_passes_count = len(active_passes)
    recent_passes = active_passes[:4]

    recent_documents = user_docs.order_by('-created_at')[:4]

    # Email verification profile status
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    context = {
        'total_documents': total_docs_count,
        'total_passes': total_passes_count,
        'active_passes': active_passes_count,
        'storage_used_mb': f"{storage_used_mb:.1f}",
        'storage_quota_mb': f"{storage_quota_mb:.0f}",
        'storage_pct': storage_pct,
        'recent_documents': recent_documents,
        'recent_passes': recent_passes,
        'is_email_verified': profile.is_email_verified,
    }
    return render(request, 'accounts/dashboard.html', context)


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
        return redirect('dashboard')

    if request.method == 'POST':
        form = ForgotPasswordRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            client_ip = get_client_ip(request)

            matched_users = User.objects.filter(email__iexact=email)
            for target_user in matched_users:
                # Rate-limit reset requests (max 1 new token per 60 seconds per user)
                recent_token = PasswordResetToken.objects.filter(
                    user=target_user,
                    created_at__gt=timezone.now() - timedelta(seconds=60)
                ).exists()

                if not recent_token:
                    token_record, raw_token = PasswordResetToken.create_token_for_user(
                        user=target_user,
                        ip_address=client_ip,
                        ttl_minutes=30
                    )
                    send_password_reset_email(target_user, raw_token, token_record.expires_at)

            return render(request, 'accounts/password_reset_done.html', {
                'submitted_email': email
            })
    else:
        form = ForgotPasswordRequestForm()

    return render(request, 'accounts/password_reset_request.html', {'form': form})


def password_reset_confirm_view(request, token):
    """
    Validates single-use reset token and permits user to set a new master passphrase.
    Invalidates session and triggers a security confirmation email upon success.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    token_record = PasswordResetToken.get_valid_token(token)
    if not token_record:
        return render(request, 'accounts/password_reset_invalid.html', status=400)

    user = token_record.user

    if request.method == 'POST':
        form = SetNewPasswordForm(user, request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['password1']
            user.set_password(new_password)
            user.save()

            # Mark token used immediately to prevent replay
            token_record.mark_used()

            # Invalidate all other reset tokens for this user
            PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

            # Send confirmation email
            send_password_reset_success_email(user, request=request)

            messages.success(
                request,
                "Your master passphrase has been successfully reset. Please sign in with your new credentials."
            )
            return redirect('login')
    else:
        form = SetNewPasswordForm(user)

    return render(request, 'accounts/password_reset_confirm.html', {
        'form': form,
        'user_obj': user,
        'token': token,
    })


# ==============================================================================
# Email Verification & OTP Views
# ==============================================================================

@login_required(login_url='login')
def verify_email_view(request):
    """
    Verifies user's email address via server-generated 6-digit OTP code.
    Enforces maximum attempts, expiration, and single-use invalidation.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.is_email_verified:
        messages.info(request, "Your email address is already verified.")
        return redirect('dashboard')

    # Look for active verification code
    active_code = EmailVerificationCode.objects.filter(
        user=request.user,
        email=request.user.email,
        is_used=False,
        expires_at__gt=timezone.now()
    ).first()

    if request.method == 'POST':
        form = EmailVerificationOTPForm(request.POST)
        if form.is_valid():
            submitted_code = form.cleaned_data['code']

            if not active_code:
                messages.error(
                    request,
                    "No active verification code found or your code has expired. Please request a new code below."
                )
            elif active_code.is_locked:
                messages.error(
                    request,
                    "Too many incorrect attempts on this code. For security, please request a new verification code."
                )
            elif active_code.verify_code(submitted_code):
                profile.is_email_verified = True
                profile.save(update_fields=['is_email_verified', 'updated_at'])

                send_verification_success_email(request.user)

                messages.success(
                    request,
                    "Email verification complete! Your account security routing is now fully operational."
                )
                return redirect('dashboard')
            else:
                remaining = max(0, active_code.max_attempts - active_code.attempts)
                if remaining > 0:
                    messages.error(
                        request,
                        f"Invalid verification code. {remaining} attempt(s) remaining before security lockout."
                    )
                else:
                    messages.error(
                        request,
                        "Maximum verification attempts exceeded. Please request a new verification code."
                    )
    else:
        form = EmailVerificationOTPForm()

    return render(request, 'accounts/verify_email.html', {
        'form': form,
        'has_active_code': bool(active_code and not active_code.is_locked),
        'user_email': request.user.email,
    })


@login_required(login_url='login')
def resend_verification_otp_view(request):
    """
    Generates and dispatches a fresh 6-digit OTP code with strict 60-second cooldown protection.
    """
    if request.method != 'POST':
        return redirect('verify_email')

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.is_email_verified:
        messages.info(request, "Your email address is already verified.")
        return redirect('dashboard')

    # Check 60-second cooldown
    recent_code = EmailVerificationCode.objects.filter(
        user=request.user,
        created_at__gt=timezone.now() - timedelta(seconds=60)
    ).first()

    if recent_code:
        messages.warning(
            request,
            "Please wait a minute before requesting another verification code."
        )
        return redirect('verify_email')

    # Invalidate previous unused codes
    EmailVerificationCode.objects.filter(user=request.user, is_used=False).update(is_used=True)

    # Generate fresh 6-digit code
    raw_otp = f"{secrets.randbelow(900000) + 100000}"
    expires_at = timezone.now() + timedelta(minutes=15)
    otp_record = EmailVerificationCode(
        user=request.user,
        email=request.user.email,
        expires_at=expires_at,
    )
    otp_record.set_code(raw_otp)
    otp_record.save()

    send_verification_otp_email(request.user, raw_otp, expires_at)

    messages.success(request, f"A fresh verification code has been dispatched to {request.user.email}.")
    return redirect('verify_email')
