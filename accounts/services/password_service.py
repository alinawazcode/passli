"""
Password change and verification service.
Handles both standard re-authenticated password changes and session-authorized email OTP resets.
Enforces database-backed exponential failure throttling, AUTH_PASSWORD_VALIDATORS,
previous-password rejection, session auth hash rotation, audit logging, and email alerts.
"""

from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash, get_user_model
from django.contrib.auth.password_validation import validate_password

from accounts.models import (
    UserProfile,
    EmailVerificationCode,
    ActionThrottle,
    AccountEvent,
)
from accounts.services.otp_service import issue_otp, verify_otp
from accounts.services.activity_service import log_account_event
from accounts.services.email_service import send_templated_email

User = get_user_model()

PASSWORD_THROTTLE_ACTION = "password_change"
THROTTLE_BASE_LOCKOUT_SECONDS = 900  # 15 minutes
THROTTLE_MAX_LOCKOUT_SECONDS = 86400  # 24 hours
PASSWORD_RESET_SESSION_KEY = "pwd_reset_authorized_at"
PASSWORD_RESET_WINDOW_MINUTES = 10


def get_password_change_throttle(user) -> tuple[bool, int, int]:
    """
    Checks if password change is currently throttled for this user.
    Returns (is_locked: bool, retry_after_minutes: int, failed_attempts: int).
    """
    throttle = ActionThrottle.objects.filter(
        user=user,
        action=PASSWORD_THROTTLE_ACTION,
    ).first()

    if not throttle or not throttle.is_locked:
        return False, 0, throttle.failed_attempts if throttle else 0

    diff = (throttle.locked_until - timezone.now()).total_seconds()
    retry_minutes = max(1, int(diff / 60 + 0.999))
    return True, retry_minutes, throttle.failed_attempts


def record_password_change_failure(user, request=None) -> tuple[int, int]:
    """
    Records a failed current-password submission in the database under atomic lock.
    Locks the action for 15 minutes on the 5th failure, doubling per failure up to 24 hours.
    Returns (total_failures: int, retry_after_seconds: int).
    """
    now = timezone.now()
    with transaction.atomic():
        throttle, _ = ActionThrottle.objects.select_for_update().get_or_create(
            user=user,
            action=PASSWORD_THROTTLE_ACTION,
            defaults={"failed_attempts": 0},
        )
        throttle.failed_attempts += 1
        failures = throttle.failed_attempts

        lockout_seconds = 0
        if failures >= 5:
            power = failures - 5
            lockout_seconds = min(
                THROTTLE_BASE_LOCKOUT_SECONDS * (2**power),
                THROTTLE_MAX_LOCKOUT_SECONDS,
            )
            throttle.locked_until = now + timedelta(seconds=lockout_seconds)

        throttle.save(update_fields=["failed_attempts", "locked_until", "updated_at"])

    log_account_event(
        user,
        AccountEvent.EventType.REAUTH_FAILED,
        request=request,
        metadata={"action": "password_change", "failures": failures},
    )

    return failures, lockout_seconds


def reset_password_change_throttle(user) -> None:
    """Resets failed attempt counters and clears locks upon successful password change."""
    ActionThrottle.objects.filter(
        user=user,
        action=PASSWORD_THROTTLE_ACTION,
    ).update(failed_attempts=0, locked_until=None)


def change_password_normal(
    user,
    current_password: str,
    new_password: str,
    confirm_password: str,
    request=None,
) -> tuple[bool, str]:
    """
    Changes user password via re-authentication with current password.
    Enforces DB failure throttle, validates similarity/length, invalidates other sessions,
    and dispatches a confirmation email.
    """
    # 1. Check DB throttle status
    is_locked, retry_minutes, _ = get_password_change_throttle(user)
    if is_locked:
        raise ValidationError(
            f"Too many failed password attempts. Password change is locked. Please try again in {retry_minutes} minute(s)."
        )

    # 2. Re-authenticate
    if not user.check_password(current_password):
        failures, _ = record_password_change_failure(user, request=request)
        is_locked_now, retry_mins, _ = get_password_change_throttle(user)
        if is_locked_now:
            raise ValidationError(
                f"Too many failed password attempts. Password change is locked. Please try again in {retry_mins} minute(s)."
            )
        remaining = max(0, 5 - failures)
        raise ValidationError(
            f"The current password entered is incorrect. {remaining} attempt(s) remaining before security lockout."
        )

    # 3. Confirmation check
    if new_password != confirm_password:
        raise ValidationError("The new passwords do not match. Please re-enter both.")

    # 4. Reject same password
    if user.check_password(new_password):
        raise ValidationError("The new password cannot be the same as your current password.")

    # 5. Run Django AUTH_PASSWORD_VALIDATORS
    validate_password(new_password, user=user)

    # 6. Apply password change and rotate auth hash
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password"])
        reset_password_change_throttle(user)

        if request:
            update_session_auth_hash(request, user)

        log_account_event(
            user,
            AccountEvent.EventType.PASSWORD_CHANGED,
            request=request,
            metadata={"method": "current_password"},
        )

    # 7. Notify verified email
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if user.email and profile.is_email_verified:
        send_templated_email(
            subject="Security Notice: Passli Vault Master Password Changed",
            template_base="password_reset_confirmation",
            context={
                "username": user.username,
                "changed_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            },
            recipient_list=[user.email],
            fail_silently=True,
        )

    return True, "Your master password has been successfully updated."


def request_password_reset_otp(user, request=None) -> tuple[bool, str]:
    """
    Sends a 6-digit OTP to the user's verified email for password reset when current password is forgotten.
    Only available if account has an existing, verified email address.
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not user.email or not profile.is_email_verified:
        raise ValidationError("An email address must be added and verified before using email OTP password reset.")

    # Issue purpose-scoped OTP
    _, raw_otp = issue_otp(
        user=user,
        email=user.email,
        purpose=EmailVerificationCode.PURPOSE_CHANGE_PASSWORD,
    )

    send_templated_email(
        subject="Passli Vault: Password Reset Verification Code",
        template_base="password_reset_otp",
        context={
            "username": user.username,
            "otp_code": raw_otp,
            "ttl_minutes": 15,
        },
        recipient_list=[user.email],
        fail_silently=True,
    )

    log_account_event(
        user,
        AccountEvent.EventType.PASSWORD_OTP_SENT,
        request=request,
    )

    return True, f"A 6-digit verification code has been dispatched to {user.email}."


def verify_password_reset_otp(user, submitted_code: str, request) -> tuple[bool, str]:
    """
    Validates submitted 6-digit OTP code for password reset.
    On success, authorizes a 10-minute session window for setting a new password.
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not user.email or not profile.is_email_verified:
        return False, "An email address must be added and verified before using email OTP password reset."

    is_valid, error_msg = verify_otp(
        user=user,
        purpose=EmailVerificationCode.PURPOSE_CHANGE_PASSWORD,
        submitted_code=submitted_code,
        email=user.email,
    )
    if not is_valid:
        return False, error_msg

    # Authorize session for 10 minutes
    request.session[PASSWORD_RESET_SESSION_KEY] = timezone.now().isoformat()
    if hasattr(request.session, "modified"):
        request.session.modified = True

    return True, "Verification successful. You may now define a new password below."


def change_password_via_otp_session(
    user,
    new_password: str,
    confirm_password: str,
    request,
) -> tuple[bool, str]:
    """
    Sets a new password using active 10-minute session authorization earned via OTP verification.
    """
    auth_str = request.session.get(PASSWORD_RESET_SESSION_KEY)
    if not auth_str:
        raise ValidationError(
            "Password reset authorization has expired or was not initiated. Please request a new code."
        )

    try:
        auth_time = datetime.fromisoformat(auth_str)
        if timezone.is_naive(auth_time):
            auth_time = timezone.make_aware(auth_time)
    except (ValueError, TypeError):
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        raise ValidationError("Invalid reset authorization. Please request a new code.")

    if timezone.now() > auth_time + timedelta(minutes=PASSWORD_RESET_WINDOW_MINUTES):
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        raise ValidationError(
            f"The {PASSWORD_RESET_WINDOW_MINUTES}-minute password reset window has expired. Please request a new code."
        )

    if new_password != confirm_password:
        raise ValidationError("The new passwords do not match. Please re-enter both.")

    if user.check_password(new_password):
        raise ValidationError("The new password cannot be the same as your current password.")

    validate_password(new_password, user=user)

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password"])
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        reset_password_change_throttle(user)

        update_session_auth_hash(request, user)

        log_account_event(
            user,
            AccountEvent.EventType.PASSWORD_CHANGED,
            request=request,
            metadata={"method": "email_otp"},
        )

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if user.email and profile.is_email_verified:
        send_templated_email(
            subject="Security Notice: Passli Vault Master Password Changed",
            template_base="password_reset_confirmation",
            context={
                "username": user.username,
                "changed_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            },
            recipient_list=[user.email],
            fail_silently=True,
        )

    return True, "Your master password has been successfully updated."
