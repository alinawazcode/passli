"""
Email change workflow service.
Never updates auth.User.email prior to successful 6-digit OTP verification.
Enforces re-authentication, non-disclosure of existing accounts (anti-enumeration),
cooldowns, dual notifications (old and new addresses), and atomic row verification.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth import get_user_model

from accounts.models import (
    UserProfile,
    EmailVerificationCode,
    PasswordResetToken,
    PendingEmailChange,
    AccountEvent,
)
from accounts.services.otp_service import issue_otp, verify_otp
from accounts.services.activity_service import log_account_event
from accounts.services.email_service import send_templated_email

User = get_user_model()


def request_email_change(
    user,
    new_email: str,
    current_password: str,
    request=None,
) -> tuple[bool, str]:
    """
    Initiates an email address update.
    Re-authenticates user, validates syntax, isolates pending email without modifying user.email,
    and dispatches a 6-digit OTP to the new email address.
    If the account already has a verified email, notifies the old address as a security precaution.
    Returns (success: bool, user_message: str).
    """
    # 1. Re-authenticate with current password
    if not user.check_password(current_password):
        log_account_event(
            user,
            AccountEvent.EventType.REAUTH_FAILED,
            request=request,
            metadata={"action": "request_email_change"},
        )
        raise ValidationError("The current password entered is incorrect.")

    # 2. Normalize and validate new email syntax
    clean_email = str(new_email).strip().lower()
    try:
        validate_email(clean_email)
    except ValidationError:
        raise ValidationError("Please provide a valid email address.")

    current_email = (user.email or "").strip().lower()
    if clean_email == current_email:
        raise ValidationError("The new email address cannot be the same as your current address.")

    # 3. Anti-enumeration: Check if already registered by another account
    already_taken = User.objects.filter(email__iexact=clean_email).exclude(pk=user.pk).exists()

    generic_success_msg = "If this address can be used, a verification code has been sent."

    if already_taken:
        # Do not reveal existence or send code to the collision address
        log_account_event(
            user,
            AccountEvent.EventType.EMAIL_CHANGE_REQUESTED,
            request=request,
            metadata={"status": "suppressed_duplicate"},
        )
        return True, generic_success_msg

    # 4. Record pending change record (NOT on user yet)
    PendingEmailChange.objects.update_or_create(
        user=user,
        defaults={"new_email": clean_email},
    )

    # 5. Issue OTP code scoped to change_email purpose
    _, raw_otp = issue_otp(
        user=user,
        email=clean_email,
        purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
    )

    # 6. Send OTP to the NEW address
    send_templated_email(
        subject="Passli Vault: Verify Your New Email Address",
        template_base="email_change_otp",
        context={
            "username": user.username,
            "new_email": clean_email,
            "otp_code": raw_otp,
            "ttl_minutes": 15,
        },
        recipient_list=[clean_email],
        fail_silently=True,
    )

    # 7. Notify OLD verified address if present
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if current_email and profile.is_email_verified:
        send_templated_email(
            subject="Security Alert: Email Change Requested for Your Passli Account",
            template_base="email_change_notice_old",
            context={
                "username": user.username,
                "old_email": current_email,
                "new_email": clean_email,
            },
            recipient_list=[current_email],
            fail_silently=True,
        )

    # 8. Log audit event
    log_account_event(
        user,
        AccountEvent.EventType.EMAIL_CHANGE_REQUESTED,
        request=request,
        metadata={"pending_email": clean_email},
    )

    return True, generic_success_msg


def confirm_email_change(
    user,
    submitted_code: str,
    request=None,
) -> tuple[bool, str]:
    """
    Validates the 6-digit OTP sent to the pending address.
    Under atomic execution, re-checks that the address remains free, updates user.email,
    marks is_email_verified=True, invalidates prior reset tokens/codes, and logs AccountEvent.
    Returns (success: bool, message: str).
    """
    with transaction.atomic():
        pending = PendingEmailChange.objects.select_for_update().filter(user=user).first()
        if not pending:
            return False, "No pending email change request found. Please request a new code."

        target_email = pending.new_email

        # 1. Verify OTP with change_email purpose
        is_valid, error_msg = verify_otp(
            user=user,
            purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
            submitted_code=submitted_code,
            email=target_email,
        )
        if not is_valid:
            return False, error_msg

        # 2. Re-verify uniqueness under atomic lock
        if User.objects.filter(email__iexact=target_email).exclude(pk=user.pk).exists():
            pending.delete()
            return False, "This email address is no longer available. Please request a change again."

        # 3. Apply change to auth.User
        old_email = user.email
        user.email = target_email
        user.save(update_fields=["email"])

        profile, _ = UserProfile.objects.select_for_update().get_or_create(user=user)
        profile.is_email_verified = True
        profile.save(update_fields=["is_email_verified", "updated_at"])

        # 4. Invalidate pending change record
        pending.delete()

        # 5. Invalidate all pending password reset tokens & other codes for this user
        PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
        EmailVerificationCode.objects.filter(user=user, is_used=False).update(is_used=True)

        # 6. Log audit event
        log_account_event(
            user,
            AccountEvent.EventType.EMAIL_CHANGED,
            request=request,
            metadata={
                "old_email": old_email,
                "new_email": target_email,
            },
        )

    # 7. Dispatches confirmation notices
    if old_email:
        send_templated_email(
            subject="Security Confirmation: Passli Account Email Address Changed",
            template_base="email_change_confirmed_old",
            context={
                "username": user.username,
                "old_email": old_email,
                "new_email": target_email,
            },
            recipient_list=[old_email],
            fail_silently=True,
        )

    send_templated_email(
        subject="Passli Vault: Email Address Verified Successfully",
        template_base="email_verified_confirmation",
        context={
            "username": user.username,
            "email": target_email,
        },
        recipient_list=[target_email],
        fail_silently=True,
    )

    return True, "Your email address has been successfully updated and verified."


def cancel_email_change(user, request=None) -> None:
    """
    Cancels any active pending email change request and invalidates unused change_email codes.
    """
    PendingEmailChange.objects.filter(user=user).delete()
    EmailVerificationCode.objects.filter(
        user=user,
        purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
        is_used=False,
    ).update(is_used=True)
