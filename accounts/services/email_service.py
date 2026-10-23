import logging
import smtplib
import socket
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, List, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse

from .user_agent import parse_user_agent

logger = logging.getLogger('accounts')


def get_base_url() -> str:
    """Returns configured, trusted APP_URL without trailing slash."""
    url = getattr(settings, 'APP_URL', 'http://localhost:8000')
    return url.rstrip('/')


def build_absolute_app_url(path: str) -> str:
    """Builds an absolute URL using the trusted configured APP_URL."""
    base = get_base_url()
    clean_path = path if path.startswith('/') else f"/{path}"
    return f"{base}{clean_path}"


def send_templated_email(
    subject: str,
    template_base: str,
    context: Dict[str, Any],
    recipient_list: List[str],
    from_email: Optional[str] = None,
    fail_silently: bool = False
) -> bool:
    """
    Renders both HTML and plain-text variants of a template and sends a multi-part email.
    Provides structured error handling, connection timeout management, and credential redaction.
    """
    if not recipient_list:
        logger.warning("Email dispatch skipped: empty recipient list.")
        return False

    sender = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@passli.dev')
    now = timezone.now()

    # Enforce safe global template context
    email_context = {
        'app_url': get_base_url(),
        'timestamp_utc': now.strftime('%Y-%m-%d %H:%M:%S'),
        'current_year': now.year,
        **context
    }

    try:
        html_template = f"emails/{template_base}.html"
        text_template = f"emails/{template_base}.txt"

        html_content = render_to_string(html_template, email_context)
        text_content = render_to_string(text_template, email_context)
    except Exception as render_err:
        logger.error(f"Failed to render email templates for {template_base}: {str(render_err)}")
        if not fail_silently:
            raise
        return False

    # Mask recipient addresses in logs to prevent PII exposure
    masked_recipients = [
        f"{r[:2]}***@{r.split('@')[-1]}" if '@' in r else "***"
        for r in recipient_list
    ]

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=sender,
            to=recipient_list
        )
        msg.attach_alternative(html_content, "text/html")
        sent_count = msg.send(fail_silently=False)

        if sent_count > 0:
            logger.info(
                f"Email successfully dispatched: subject='{subject}', recipients={masked_recipients}, "
                f"template='{template_base}'"
            )
            return True
        else:
            logger.warning(
                f"Email provider accepted 0 messages: subject='{subject}', recipients={masked_recipients}"
            )
            return False

    except (smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError) as auth_err:
        logger.error(
            f"SMTP Authentication/Connection failure during email dispatch: code={getattr(auth_err, 'smtp_code', 'N/A')}, "
            f"recipients={masked_recipients}. Please check SMTP_USER and SMTP_PASS App Password settings."
        )
        if not fail_silently:
            raise
        return False
    except (smtplib.SMTPException, socket.error, OSError) as smtp_err:
        # If default port is 465 (SSL) and failed due to network / firewall, attempt fallback to port 587 STARTTLS
        if getattr(settings, 'EMAIL_PORT', 465) == 465 and getattr(settings, 'EMAIL_BACKEND', '').endswith('smtp.EmailBackend'):
            logger.warning(
                f"SMTP connection to port 465 failed ({type(smtp_err).__name__}). "
                "Attempting automatic fallback via port 587 STARTTLS..."
            )
            try:
                from django.core.mail import get_connection
                fallback_conn = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host=settings.EMAIL_HOST,
                    port=587,
                    username=settings.EMAIL_HOST_USER,
                    password=settings.EMAIL_HOST_PASSWORD,
                    use_tls=True,
                    use_ssl=False,
                    timeout=settings.EMAIL_TIMEOUT,
                )
                msg.connection = fallback_conn
                sent_count = msg.send(fail_silently=False)
                if sent_count > 0:
                    logger.info(
                        f"Email successfully dispatched via port 587 STARTTLS fallback: "
                        f"subject='{subject}', recipients={masked_recipients}"
                    )
                    return True
            except Exception as fb_err:
                logger.error(f"Port 587 fallback failed as well: {type(fb_err).__name__} - {fb_err}")

        logger.error(
            f"SMTP Transport error during email dispatch: {type(smtp_err).__name__} - {str(smtp_err)}, "
            f"recipients={masked_recipients}"
        )
        if not fail_silently:
            raise
        return False
    except Exception as generic_err:
        logger.error(
            f"Unexpected exception during email dispatch: {type(generic_err).__name__} - {str(generic_err)}, "
            f"recipients={masked_recipients}"
        )
        if not fail_silently:
            raise
        return False


def send_verification_otp_email(user, otp_code: str, expires_at: datetime) -> bool:
    """
    Dispatches 6-digit verification OTP code to user's registered email.
    """
    if not user.email:
        return False

    context = {
        'username': user.username,
        'otp_code': otp_code,
        'expires_at_utc': expires_at.strftime('%H:%M:%S'),
    }

    return send_templated_email(
        subject="Passli Vault: Your Email Verification Code",
        template_base="email_verification_otp",
        context=context,
        recipient_list=[user.email],
        fail_silently=True
    )


def send_verification_success_email(user) -> bool:
    """
    Confirms email ownership verification and active security routing.
    """
    if not user.email:
        return False

    dashboard_url = build_absolute_app_url(reverse('dashboard'))
    context = {
        'username': user.username,
        'email': user.email,
        'dashboard_url': dashboard_url,
    }

    return send_templated_email(
        subject="Passli Vault: Email Address Verified Successfully",
        template_base="email_verified_confirmation",
        context=context,
        recipient_list=[user.email],
        fail_silently=True
    )


def send_password_reset_email(user, reset_token: str, expires_at: datetime) -> bool:
    """
    Sends cryptographically random, single-use password reset link.
    """
    if not user.email:
        return False

    reset_path = reverse('password_reset_confirm', kwargs={'token': reset_token})
    reset_url = build_absolute_app_url(reset_path)

    context = {
        'username': user.username,
        'reset_url': reset_url,
        'expires_at_utc': expires_at.strftime('%Y-%m-%d %H:%M:%S'),
    }

    return send_templated_email(
        subject="Passli Vault: Password Reset Request",
        template_base="password_reset",
        context=context,
        recipient_list=[user.email],
        fail_silently=True
    )


def send_password_reset_success_email(user, request=None) -> bool:
    """
    Confirms master password change with client metadata and security advice.
    """
    if not user.email:
        return False

    login_url = build_absolute_app_url(reverse('login'))

    ip_address = 'Unavailable'
    ua_info = {'browser': 'Unknown', 'os': 'Unknown', 'device_type': 'Desktop'}

    if request:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        ip_address = x_forwarded.split(',')[0].strip() if x_forwarded else request.META.get('REMOTE_ADDR', 'Unavailable')
        ua_info = parse_user_agent(request.META.get('HTTP_USER_AGENT'))

    context = {
        'username': user.username,
        'login_url': login_url,
        'ip_address': ip_address,
        'browser': ua_info.get('browser', 'Unknown Browser'),
        'os': ua_info.get('os', 'Unknown OS'),
        'device_type': ua_info.get('device_type', 'Desktop'),
    }

    return send_templated_email(
        subject="Security Notice: Passli Vault Master Password Changed",
        template_base="password_reset_confirmation",
        context=context,
        recipient_list=[user.email],
        fail_silently=True
    )


def send_security_alert_failed_passcode(share_pass, request, attempts_count: int) -> bool:
    """
    Sends failed QR / passcode attempt alert to the SharePass owner's verified email.
    """
    owner = share_pass.owner
    if not owner or not owner.email:
        logger.info(f"Failed passcode security alert suppressed: pass {share_pass.id} owner has no email.")
        return False

    # Inferred IP
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR') if request else None
    if x_forwarded:
        client_ip = x_forwarded.split(',')[0].strip()
    elif request:
        client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
    else:
        client_ip = 'Unknown'

    # Inferred User-Agent details
    user_agent_str = request.META.get('HTTP_USER_AGENT', '') if request else ''
    ua_info = parse_user_agent(user_agent_str)

    pass_title = share_pass.title or f"Pass #{str(share_pass.id)[:8]}"
    pass_manage_path = reverse('share_detail', kwargs={'pass_id': share_pass.id})
    pass_manage_url = build_absolute_app_url(pass_manage_path)

    context = {
        'owner_name': owner.username,
        'pass_title': pass_title,
        'pass_id': str(share_pass.id),
        'attempts_count': attempts_count,
        'ip_address': client_ip,
        'browser': ua_info.get('browser', 'Web Browser'),
        'os': ua_info.get('os', 'Unknown OS'),
        'device_type': ua_info.get('device_type', 'Desktop'),
        'pass_manage_url': pass_manage_url,
    }

    return send_templated_email(
        subject=f"Security Alert: Failed QR Passcode Attempts ({pass_title})",
        template_base="failed_passcode_alert",
        context=context,
        recipient_list=[owner.email],
        fail_silently=True
    )


def send_welcome_email(user) -> bool:
    """
    Sends welcome orientation email to newly registered vault owner.
    """
    if not user.email:
        return False

    dashboard_url = build_absolute_app_url(reverse('dashboard'))
    context = {
        'username': user.username,
        'dashboard_url': dashboard_url,
    }

    return send_templated_email(
        subject="Welcome to Passli: Your Personal Vault is Ready",
        template_base="welcome_registered",
        context=context,
        recipient_list=[user.email],
        fail_silently=True
    )


def check_and_send_failed_passcode_alert(share_pass, request, failures_count: int) -> bool:
    """
    Evaluates failure threshold and rate limiting cooldown.
    If threshold met (>= 3 attempts) and cooldown has elapsed, sends security alert to owner.
    """
    if failures_count < 3:
        return False

    owner = share_pass.owner
    if not owner or not owner.email:
        return False

    # Inferred IP using TRUSTED_PROXY_COUNT and validation
    from audit.models import get_client_ip
    client_ip = get_client_ip(request)

    from accounts.models import SecurityAlertLog
    identifier = f"pass:{share_pass.id}"

    should_send, total_failures = SecurityAlertLog.check_and_record_alert(
        alert_type='failed_passcode',
        identifier=identifier,
        recipient_email=owner.email,
        ip_address=client_ip,
        cooldown_seconds=900  # 15 minute cooldown between emails
    )

    if should_send:
        return send_security_alert_failed_passcode(share_pass, request, attempts_count=total_failures)

    return False
