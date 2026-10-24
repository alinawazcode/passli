"""
Comprehensive Test Suite for Email Integration, Verification OTPs, Password Recovery,
and Failed Passcode Security Alerts.
"""

import smtplib
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from accounts.models import UserProfile, EmailVerificationCode, PasswordResetToken, SecurityAlertLog
from accounts.emails import (
    send_templated_email,
    send_verification_otp_email,
    send_verification_success_email,
    send_password_reset_email,
    send_password_reset_success_email,
    send_security_alert_failed_passcode,
    check_and_send_failed_passcode_alert,
    build_absolute_app_url,
    get_base_url,
)
from accounts.services.user_agent import parse_user_agent
from documents.models import Document
from sharing.models import SharePass
from sharing.utils import generate_share_key
from tests.unit import get_test_password

User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    APP_URL='https://passli.example.com'
)
class EmailIntegrationServiceTests(TestCase):
    """Tests covering SMTP email service dispatch, multi-part rendering, and safe failure handling."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username='service_tester',
            email='tester@passli.dev',
            password=self.password
        )

    def test_app_url_and_link_builder(self):
        """Verify build_absolute_app_url constructs trusted HTTPS URLs using APP_URL."""
        self.assertEqual(get_base_url(), 'https://passli.example.com')
        url = build_absolute_app_url('/password-reset/confirm/abc123xyz/')
        self.assertEqual(url, 'https://passli.example.com/password-reset/confirm/abc123xyz/')

    def test_send_templated_email_renders_html_and_text(self):
        """Verify templated emails produce both HTML and plain-text alternatives."""
        mail.outbox = []
        sent = send_templated_email(
            subject="Test Multi-part Subject",
            template_base="email_verification_otp",
            context={
                'username': self.user.username,
                'otp_code': '987654',
                'expires_at_utc': '12:00:00',
            },
            recipient_list=[self.user.email]
        )
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "Test Multi-part Subject")
        self.assertIn("987654", msg.body)  # Plain-text body
        self.assertTrue(any(content_type == "text/html" for _, content_type in msg.alternatives))

    def test_send_templated_email_empty_recipients_fails_gracefully(self):
        """Verify empty recipient list returns False without error."""
        sent = send_templated_email(
            subject="Subject",
            template_base="welcome_registered",
            context={},
            recipient_list=[]
        )
        self.assertFalse(sent)

    def test_smtp_auth_error_handling(self):
        """Verify SMTPAuthenticationError is caught safely without raising unhandled exception."""
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=smtplib.SMTPAuthenticationError(535, b'Authentication failed')):
            sent = send_templated_email(
                subject="Test Auth Error",
                template_base="welcome_registered",
                context={'username': self.user.username, 'dashboard_url': 'http://localhost'},
                recipient_list=[self.user.email],
                fail_silently=True
            )
            self.assertFalse(sent)

    def test_smtp_transport_error_handling(self):
        """Verify network connection and transport errors are caught safely."""
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=smtplib.SMTPConnectError(421, b'Connection refused')):
            sent = send_templated_email(
                subject="Test Connect Error",
                template_base="welcome_registered",
                context={'username': self.user.username, 'dashboard_url': 'http://localhost'},
                recipient_list=[self.user.email],
                fail_silently=True
            )
            self.assertFalse(sent)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    APP_URL='https://passli.example.com'
)
class UserRegistrationAndEmailOTPTests(TestCase):
    """Tests covering registration, auto-creation of OTP codes, verification flow, and attempt limits."""

    def setUp(self):
        self.client = Client()
        mail.outbox = []

    def test_register_creates_profile_and_sends_verification_otp(self):
        """Verify new registration creates profile, generates OTP code, and dispatches email."""
        reg_pw = get_test_password()
        reg_data = {
            'username': 'registered_hero',
            'email': 'hero@passli.dev',
            'password1': reg_pw,
            'password2': reg_pw,
        }
        response = self.client.post(reverse('register'), data=reg_data, follow=True)
        self.assertEqual(response.status_code, 200)

        user = User.objects.get(username='registered_hero')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertFalse(user.profile.is_email_verified)

        # Check OTP record created
        otp_records = EmailVerificationCode.objects.filter(user=user)
        self.assertEqual(otp_records.count(), 1)
        otp = otp_records.first()
        self.assertFalse(otp.is_used)
        self.assertGreater(otp.expires_at, timezone.now())

        # Check email sent
        self.assertGreaterEqual(len(mail.outbox), 1)
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any('Verification Code' in s for s in subjects))

    def test_verify_email_otp_success_updates_profile(self):
        """Verify entering the correct 6-digit OTP code sets is_email_verified to True."""
        user = User.objects.create_user(username='otp_user', email='otp@passli.dev', password=get_test_password())
        code_record = EmailVerificationCode(
            user=user,
            email=user.email,
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        code_record.set_code('654321')
        code_record.save()

        self.client.force_login(user)
        mail.outbox = []

        response = self.client.post(reverse('verify_email'), {'code': '654321'}, follow=True)
        self.assertEqual(response.status_code, 200)

        user.profile.refresh_from_db()
        self.assertTrue(user.profile.is_email_verified)

        code_record.refresh_from_db()
        self.assertTrue(code_record.is_used)

        # Check confirmation email was sent
        self.assertTrue(any('Verified Successfully' in m.subject for m in mail.outbox))

    def test_verify_email_otp_invalid_code_decrements_remaining(self):
        """Verify invalid OTP submission increments attempt counter and returns remaining attempts."""
        user = User.objects.create_user(username='otp_fail_user', email='fail@passli.dev', password=get_test_password())
        code_record = EmailVerificationCode(
            user=user,
            email=user.email,
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        code_record.set_code('112233')
        code_record.save()

        self.client.force_login(user)

        response = self.client.post(reverse('verify_email'), {'code': '999999'}, follow=True)
        self.assertEqual(response.status_code, 200)

        code_record.refresh_from_db()
        self.assertEqual(code_record.attempts, 1)
        self.assertContains(response, '4 attempt(s) remaining')

    def test_verify_email_otp_lockout_after_max_attempts(self):
        """Verify 5 failed OTP attempts locks out the code."""
        user = User.objects.create_user(username='otp_lock_user', email='lock@passli.dev', password=get_test_password())
        code_record = EmailVerificationCode(
            user=user,
            email=user.email,
            expires_at=timezone.now() + timedelta(minutes=15),
            attempts=4
        )
        code_record.set_code('112233')
        code_record.save()

        self.client.force_login(user)

        response = self.client.post(reverse('verify_email'), {'code': '999999'}, follow=True)
        self.assertEqual(response.status_code, 200)

        code_record.refresh_from_db()
        self.assertEqual(code_record.attempts, 5)
        self.assertTrue(code_record.is_locked)
        self.assertContains(response, 'Maximum verification attempts exceeded')

    def test_resend_verification_otp_cooldown(self):
        """Verify resend enforces 60-second cooldown."""
        user = User.objects.create_user(username='resend_user', email='resend@passli.dev', password=get_test_password())
        EmailVerificationCode.objects.create(
            user=user,
            email=user.email,
            expires_at=timezone.now() + timedelta(minutes=15),
            created_at=timezone.now()
        )

        self.client.force_login(user)
        mail.outbox = []

        response = self.client.post(reverse('resend_verification_otp'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please wait a minute before requesting another verification code')
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    APP_URL='https://passli.example.com'
)
class ForgotPasswordAndResetTests(TestCase):
    """Tests covering password reset initiation, token generation, anti-enumeration, and updates."""

    def setUp(self):
        self.client = Client()
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username='reset_target',
            email='reset_target@passli.dev',
            password=self.password
        )
        mail.outbox = []

    def test_forgot_password_for_existing_user_dispatches_email(self):
        """Verify forgot-password for registered email creates hashed token and sends reset link."""
        response = self.client.post(reverse('password_reset'), {'email': 'reset_target@passli.dev'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/password_reset_done.html')

        tokens = PasswordResetToken.objects.filter(user=self.user)
        self.assertEqual(tokens.count(), 1)
        token_record = tokens.first()
        self.assertFalse(token_record.is_used)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "Passli Vault: Password Reset Request")
        self.assertIn("password-reset/confirm/", msg.body)
        self.assertIn("https://passli.example.com", msg.body)

    def test_forgot_password_for_nonexistent_email_prevents_enumeration(self):
        """Verify nonexistent email returns identical success template without dispatching email."""
        response = self.client.post(reverse('password_reset'), {'email': 'nonexistent@passli.dev'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/password_reset_done.html')
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_with_valid_token(self):
        """Verify valid token updates user password, marks token used, and sends confirmation email."""
        record, raw_token = PasswordResetToken.create_token_for_user(self.user)
        url = reverse('password_reset_confirm', kwargs={'token': raw_token})

        # Render form
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/password_reset_confirm.html')

        mail.outbox = []
        new_pw = get_test_password()
        new_data = {
            'password1': new_pw,
            'password2': new_pw,
        }
        post_response = self.client.post(url, data=new_data, follow=True)
        self.assertRedirects(post_response, reverse('login'))

        # Check token used
        record.refresh_from_db()
        self.assertTrue(record.is_used)

        # Check password actually changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_pw))

        # Check confirmation email
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Security Notice: Passli Vault Master Password Changed")

    def test_password_reset_confirm_replay_rejected(self):
        """Verify used token is rejected on replay."""
        record, raw_token = PasswordResetToken.create_token_for_user(self.user)
        record.mark_used()

        url = reverse('password_reset_confirm', kwargs={'token': raw_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, 'accounts/password_reset_invalid.html')

    def test_password_reset_confirm_expired_token_rejected(self):
        """Verify expired token is rejected."""
        record, raw_token = PasswordResetToken.create_token_for_user(self.user)
        record.expires_at = timezone.now() - timedelta(minutes=5)
        record.save()

        url = reverse('password_reset_confirm', kwargs={'token': raw_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, 'accounts/password_reset_invalid.html')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    APP_URL='https://passli.example.com'
)
class FailedPasscodeSecurityAlertTests(TestCase):
    """Tests covering security alerts on failed QR/passcode verification, rate limiting, and device parsing."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='alert_owner',
            email='alert_owner@passli.dev',
            password=get_test_password()
        )
        self.raw_key = generate_share_key()
        self.share_pass = SharePass.objects.create(
            owner=self.owner,
            title='Financial Records Pass',
            expires_at=timezone.now() + timedelta(hours=2)
        )
        self.share_pass.set_key(self.raw_key)
        self.share_pass.save()
        mail.outbox = []

    def test_user_agent_parser(self):
        """Verify user_agent parser extracts browser, OS, and device type cleanly."""
        ua_chrome_win = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        info = parse_user_agent(ua_chrome_win)
        self.assertEqual(info['browser'], 'Google Chrome')
        self.assertEqual(info['os'], 'Windows 10/11')
        self.assertEqual(info['device_type'], 'Desktop')

        ua_iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
        info_mobile = parse_user_agent(ua_iphone)
        self.assertEqual(info_mobile['device_type'], 'Mobile')
        self.assertEqual(info_mobile['os'], 'iOS (iPhone)')

        info_none = parse_user_agent(None)
        self.assertEqual(info_none['browser'], 'Unknown Browser')

    def test_failed_passcode_attempts_trigger_security_alert_at_threshold(self):
        """Verify consecutive failed attempts on /p/<pass_id>/ trigger security email to pass owner."""
        url = reverse('recipient_verify', kwargs={'pass_id': self.share_pass.id})

        # Submit 3 failed attempts
        for i in range(1, 4):
            self.client.post(url, {'access_key': f'WRONG{i}'})

        # On the 3rd attempt, email should have been sent to owner
        self.assertGreaterEqual(len(mail.outbox), 1)
        alert_email = mail.outbox[0]
        self.assertIn("Security Alert: Failed QR Passcode Attempts", alert_email.subject)
        self.assertEqual(alert_email.to, [self.owner.email])
        self.assertIn("Financial Records Pass", alert_email.body)
        self.assertIn("Authentication Status: FAILED", alert_email.body)

    def test_security_alert_cooldown_prevents_email_flooding(self):
        """Verify cooldown suppresses duplicate emails within 15-minute window while accumulating count."""
        url = reverse('recipient_verify', kwargs={'pass_id': self.share_pass.id})

        # 3 attempts trigger first alert
        for i in range(3):
            self.client.post(url, {'access_key': f'WRONG{i}'})

        self.assertEqual(len(mail.outbox), 1)

        # 4th and 5th attempts in same session should NOT send duplicate email
        self.client.post(url, {'access_key': 'WRONG4'})
        self.client.post(url, {'access_key': 'WRONG5'})

        self.assertEqual(len(mail.outbox), 1)

        # But SecurityAlertLog records the accumulated count
        log = SecurityAlertLog.objects.get(identifier=f"pass:{self.share_pass.id}")
        self.assertGreater(log.attempts_count, 1)


class Phase2SettingsAndEmailTests(TestCase):
    """Tests covering PythonAnywhere settings: APP_URL validation, console email fallback, and credentials leak protection."""

    def test_app_url_validation_in_production(self):
        """In production (DEBUG=False), empty or localhost APP_URL raises ImproperlyConfigured."""
        from django.core.exceptions import ImproperlyConfigured
        from config.settings import validate_app_url

        # Empty URL raises
        with self.assertRaises(ImproperlyConfigured):
            validate_app_url(debug=False, url="")

        # Localhost URL raises
        with self.assertRaises(ImproperlyConfigured):
            validate_app_url(debug=False, url="http://localhost:8000")

        with self.assertRaises(ImproperlyConfigured):
            validate_app_url(debug=False, url="http://127.0.0.1:8000")

        # Valid HTTPS origin passes without exception
        try:
            validate_app_url(debug=False, url="https://demouser.pythonanywhere.com")
        except ImproperlyConfigured:
            self.fail("validate_app_url unexpectedly raised ImproperlyConfigured for valid HTTPS origin")

        # In DEBUG=True, localhost or empty does not raise
        try:
            validate_app_url(debug=True, url="")
            validate_app_url(debug=True, url="http://localhost:8000")
        except ImproperlyConfigured:
            self.fail("validate_app_url should not raise when DEBUG=True")

    def test_email_disabled_banner_rendered_when_email_service_disabled(self):
        """When EMAIL_SERVICE_CONFIGURED is False, register and password-reset pages render a warning banner."""
        client = Client()

        with self.settings(EMAIL_SERVICE_CONFIGURED=False):
            res_reg = client.get(reverse('register'))
            self.assertEqual(res_reg.status_code, 200)
            self.assertContains(res_reg, 'data-testid="email-disabled-banner"')
            self.assertContains(res_reg, "Outbound email service is disabled")

            res_reset = client.get(reverse('password_reset'))
            self.assertEqual(res_reset.status_code, 200)
            self.assertContains(res_reset, 'data-testid="email-disabled-banner"')
            self.assertContains(res_reset, "Outbound email service is disabled")

        with self.settings(EMAIL_SERVICE_CONFIGURED=True):
            res_reg_on = client.get(reverse('register'))
            self.assertNotContains(res_reg_on, 'data-testid="email-disabled-banner"')

            res_reset_on = client.get(reverse('password_reset'))
            self.assertNotContains(res_reset_on, 'data-testid="email-disabled-banner"')

    def test_no_smtp_password_in_logs_or_error_pages(self):
        """Assert that no SMTP password value ever appears in log output or error pages."""
        import logging
        from io import StringIO
        from unittest.mock import patch
        import smtplib
        from accounts.emails import send_templated_email

        secret_smtp_pass = "super-secret-smtp-app-password-xyz99"
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)

        target_logger = logging.getLogger('accounts')
        target_logger.addHandler(handler)

        try:
            with self.settings(EMAIL_HOST_PASSWORD=secret_smtp_pass):
                with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=smtplib.SMTPAuthenticationError(535, b'Authentication failed')):
                    send_templated_email(
                        subject="Test Subject",
                        recipient_list=["test@passli.dev"],
                        template_base="email_verification_otp",
                        context={'code': '123456', 'valid_minutes': 10},
                        fail_silently=True
                    )

            output = log_stream.getvalue()
            self.assertNotIn(secret_smtp_pass, output)
        finally:
            target_logger.removeHandler(handler)
