import secrets


def get_test_password() -> str:
    """Generates a secure, dynamic test password meeting all auth requirements at runtime."""
    return f"{secrets.token_urlsafe(16)}!1Aa"
