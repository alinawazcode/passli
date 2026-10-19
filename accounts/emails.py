# Expose email service functions at accounts package level
from .services.email_service import (
    send_templated_email,
    send_verification_otp_email,
    send_verification_success_email,
    send_password_reset_email,
    send_password_reset_success_email,
    send_security_alert_failed_passcode,
    check_and_send_failed_passcode_alert,
    send_welcome_email,
    build_absolute_app_url,
    get_base_url,
)

__all__ = [
    'send_templated_email',
    'send_verification_otp_email',
    'send_verification_success_email',
    'send_password_reset_email',
    'send_password_reset_success_email',
    'send_security_alert_failed_passcode',
    'check_and_send_failed_passcode_alert',
    'send_welcome_email',
    'build_absolute_app_url',
    'get_base_url',
]
