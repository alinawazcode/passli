"""
Username change and policy enforcement service.
Implements 30-day change cooldowns, reserved word blocking, '@' delimiter prohibition,
concurrency-safe row locking, audit event logging, and email notification.
"""

from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.auth import get_user_model

from config.db_utils import atomic_immediate
from accounts.models import UserProfile, AccountEvent
from accounts.services.activity_service import log_account_event
from accounts.services.email_service import send_templated_email

User = get_user_model()

USERNAME_COOLDOWN_DAYS = 30
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30

RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "root",
    "support",
    "passli",
    "system",
    "superuser",
    "owner",
    "security",
    "help",
    "api",
    "staff",
    "mod",
    "moderator",
    "null",
    "undefined",
    "test",
    "guest",
    "user",
    "settings",
    "account",
    "dashboard",
}


def get_username_cooldown_status(user) -> dict:
    """
    Evaluates whether the user is eligible to change their username.
    Returns:
        {
            'can_change': bool,
            'next_change_date': datetime | None,
            'days_remaining': int,
        }
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not profile.username_changed_at:
        return {
            "can_change": True,
            "next_change_date": None,
            "days_remaining": 0,
        }

    next_change = profile.username_changed_at + timedelta(days=USERNAME_COOLDOWN_DAYS)
    now = timezone.now()
    if now >= next_change:
        return {
            "can_change": True,
            "next_change_date": None,
            "days_remaining": 0,
        }

    remaining = (next_change - now).total_seconds()
    days_left = max(1, int(remaining / 86400 + 0.999))
    return {
        "can_change": False,
        "next_change_date": next_change,
        "days_remaining": days_left,
    }


def validate_username_format(new_username: str, current_user=None) -> str:
    """
    Validates username against format, length, reserved words, '@' prohibition,
    and case-insensitive uniqueness.
    """
    clean_username = str(new_username).strip()

    if len(clean_username) < USERNAME_MIN_LENGTH or len(clean_username) > USERNAME_MAX_LENGTH:
        raise ValidationError(f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters.")

    if "@" in clean_username:
        raise ValidationError("Usernames cannot contain the '@' symbol.")

    validator = UnicodeUsernameValidator()
    validator(clean_username)

    if clean_username.lower() in RESERVED_USERNAMES:
        raise ValidationError(f"The username '{clean_username}' is reserved and cannot be claimed.")

    qs = User.objects.filter(username__iexact=clean_username)
    if current_user:
        qs = qs.exclude(pk=current_user.pk)
    if qs.exists():
        raise ValidationError(f"The username '{clean_username}' is already in use.")

    return clean_username


def change_username(user, new_username: str, current_password: str, request=None) -> User:
    """
    Safely changes a user's username under a profile row lock with re-authentication.
    Enforces the 30-day cooldown, records an AccountEvent, and dispatches an email notice.
    """
    # 1. Re-authenticate with current password
    if not user.check_password(current_password):
        log_account_event(
            user,
            AccountEvent.EventType.REAUTH_FAILED,
            request=request,
            metadata={"action": "change_username"},
        )
        raise ValidationError("The current password entered is incorrect.")

    # 2. Validate format and uniqueness
    validated_username = validate_username_format(new_username, current_user=user)

    if validated_username == user.username:
        raise ValidationError("The new username must be different from your current username.")

    # 3. Concurrency-safe atomic execution under row lock
    with atomic_immediate():
        profile = UserProfile.objects.select_for_update().get_or_create(user=user)[0]

        now = timezone.now()
        if profile.username_changed_at:
            next_allowed = profile.username_changed_at + timedelta(days=USERNAME_COOLDOWN_DAYS)
            if now < next_allowed:
                formatted_date = next_allowed.strftime("%d %b %Y")
                raise ValidationError(f"You can change your username again on {formatted_date}.")

        old_username = user.username
        user.username = validated_username
        user.save(update_fields=["username"])

        profile.username_changed_at = now
        profile.save(update_fields=["username_changed_at", "updated_at"])

        # 4. Log audit event
        log_account_event(
            user,
            AccountEvent.EventType.USERNAME_CHANGED,
            request=request,
            metadata={
                "old_username": old_username,
                "new_username": validated_username,
            },
        )

    # 5. Dispatch notification to verified email if one exists
    if user.email and profile.is_email_verified:
        send_templated_email(
            subject="Security Notice: Passli Vault Username Changed",
            template_base="username_changed_notice",
            context={
                "username": validated_username,
                "old_username": old_username,
                "new_username": validated_username,
                "changed_at": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            },
            recipient_list=[user.email],
            fail_silently=True,
        )

    return user
