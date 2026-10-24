"""
Purpose-scoped One-Time Password (OTP) lifecycle service.
Handles cryptographic hashing, expiration, attempt tracking, cross-purpose isolation,
resend cooldowns, and hourly dispatch caps.
"""

import secrets
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import EmailVerificationCode

OTP_TTL_MINUTES = 15
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_HOURLY_USER_LIMIT = 5


def issue_otp(
    user,
    email: str,
    purpose: str = EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
) -> tuple[EmailVerificationCode, str]:
    """
    Generates and persists a hashed single-use 6-digit OTP code scoped to a specific purpose.
    Enforces a 60-second resend cooldown and a maximum of 5 generated codes per user per hour.
    Returns (code_record, raw_otp).
    """
    now = timezone.now()
    clean_email = email.strip().lower()

    # 1. Check 60-second cooldown for this user and purpose
    recent_code = EmailVerificationCode.objects.filter(
        user=user,
        purpose=purpose,
        created_at__gt=now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS),
    ).first()
    if recent_code:
        elapsed = (now - recent_code.created_at).total_seconds()
        remaining = max(1, int(OTP_RESEND_COOLDOWN_SECONDS - elapsed))
        raise ValidationError(f"Please wait {remaining} seconds before requesting another code.")

    # 2. Check hourly limit: max 5 codes per user per hour for this purpose
    hourly_count = EmailVerificationCode.objects.filter(
        user=user,
        purpose=purpose,
        created_at__gt=now - timedelta(hours=1),
    ).count()
    if hourly_count >= OTP_HOURLY_USER_LIMIT:
        raise ValidationError("Maximum code request limit reached (5 codes per hour). Please try again later.")

    # 3. Invalidate prior active, unused codes for this user and purpose
    EmailVerificationCode.objects.filter(
        user=user,
        purpose=purpose,
        is_used=False,
    ).update(is_used=True)

    # 4. Generate cryptographically random 6-digit numeric OTP
    raw_otp = f"{secrets.randbelow(900000) + 100000}"
    expires_at = now + timedelta(minutes=OTP_TTL_MINUTES)

    record = EmailVerificationCode(
        user=user,
        email=clean_email,
        purpose=purpose,
        max_attempts=OTP_MAX_ATTEMPTS,
        expires_at=expires_at,
    )
    record.set_code(raw_otp)
    record.save()

    return record, raw_otp


def verify_otp(
    user,
    purpose: str,
    submitted_code: str,
    email: str | None = None,
) -> tuple[bool, str]:
    """
    Validates a submitted 6-digit OTP code for the given user and specific purpose.
    Strictly prevents cross-purpose reuse, validates expiry, tracks attempts,
    and marks code as single-use upon successful verification.

    Returns (is_valid: bool, error_message: str).
    """
    raw_code = str(submitted_code).strip()
    if not raw_code.isdigit() or len(raw_code) != 6:
        return False, "Please enter a valid 6-digit numeric verification code."

    qs = EmailVerificationCode.objects.filter(
        user=user,
        purpose=purpose,
        is_used=False,
        expires_at__gt=timezone.now(),
    )
    if email:
        qs = qs.filter(email__iexact=email.strip().lower())

    active_code = qs.order_by("-created_at").first()
    if not active_code:
        return False, "Verification code has expired or is invalid. Please request a new code."

    if active_code.is_locked:
        return False, "Maximum verification attempts exceeded. Please request a new code."

    is_correct = active_code.verify_code(raw_code)
    if is_correct:
        return True, ""

    remaining = max(0, active_code.max_attempts - active_code.attempts)
    if remaining > 0:
        return False, f"Invalid code. {remaining} attempt(s) remaining."
    return False, "Maximum verification attempts exceeded. Please request a new code."
