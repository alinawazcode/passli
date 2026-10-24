"""
Audit and security event logging service for Passli user accounts.
Maintains structured, immutable AccountEvent records without persisting sensitive secrets.
"""

from typing import Any
from django.contrib.auth import get_user_model
from audit.models import get_client_ip
from accounts.models import AccountEvent

User = get_user_model()

SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "passphrase",
    "token",
    "secret",
    "otp",
    "code",
    "credential",
)


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """
    Strips sensitive credentials, passwords, raw OTPs, and tokens from event metadata.
    """
    if not metadata:
        return {}
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        key_lower = str(key).lower()
        if any(bad in key_lower for bad in SENSITIVE_KEY_SUBSTRINGS):
            continue
        clean[str(key)] = value
    return clean


def log_account_event(
    user,
    event_type: str,
    request=None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AccountEvent:
    """
    Creates and persists an immutable AccountEvent audit record.
    """
    client_ip = ip_address
    client_ua = user_agent or ""

    if request:
        if not client_ip:
            client_ip = get_client_ip(request)
        if not client_ua:
            client_ua = request.META.get("HTTP_USER_AGENT", "")

    # Truncate user_agent to max 200 chars per model definition
    client_ua = str(client_ua)[:200]

    clean_meta = sanitize_metadata(metadata)

    return AccountEvent.objects.create(
        user=user,
        event_type=event_type,
        ip_address=client_ip,
        user_agent=client_ua,
        metadata=clean_meta,
    )
