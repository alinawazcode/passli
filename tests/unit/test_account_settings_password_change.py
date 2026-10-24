"""
Unit tests for Account Settings Phase 4: Password Change Workflows.
Verifies both normal re-authenticated password change and OTP-based reset,
database failure throttling, multi-session invalidation, 10-minute window,
notification dispatch, and zero credential exposure in logs or audit metadata.
"""

import io
import logging
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from accounts.models import (
    UserProfile,
    EmailVerificationCode,
    ActionThrottle,
    AccountEvent,
)
from accounts.services.password_service import (
    PASSWORD_RESET_SESSION_KEY,
    PASSWORD_THROTTLE_ACTION,
)
from tests.unit import get_test_password

User = get_user_model()


class PasswordChangeWorkflowTests(TestCase):
    def setUp(self):
        self.old_password = get_test_password()
        self.new_password = get_test_password()
        self.user = User.objects.create_user(
            username="vaultkeeper",
            email="keeper@example.com",
            password=self.old_password,
        )
        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={"is_email_verified": True},
        )
        self.profile.is_email_verified = True
        self.profile.save()

        self.client.login(username="vaultkeeper", password=self.old_password)

    def test_password_change_normal_success(self):
        """User can change password with current password; receives confirmation email."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": self.old_password,
                "new_password": self.new_password,
                "confirm_password": self.new_password,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # 1. Assert user can authenticate with new password
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

        # 2. Assert confirmation email sent to verified address
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("keeper@example.com", mail.outbox[0].to)
        self.assertIn("Password Changed", mail.outbox[0].subject)

        # 3. Assert AccountEvent logged
        event = AccountEvent.objects.filter(
            user=self.user,
            event_type=AccountEvent.EventType.PASSWORD_CHANGED,
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.metadata.get("method"), "current_password")

    def test_password_change_same_password_rejected(self):
        """Rejecting new password equal to current password."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": self.old_password,
                "new_password": self.old_password,
                "confirm_password": self.old_password,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("cannot be the same" in msg.lower() for msg in messages))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_password_change_validators_enforced(self):
        """AUTH_PASSWORD_VALIDATORS reject weak passwords (e.g., too short or common)."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": self.old_password,
                "new_password": "short",
                "confirm_password": "short",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("too short" in msg.lower() or "character" in msg.lower() for msg in messages))

    def test_password_change_mismatched_confirmation(self):
        """Mismatched confirmation password fails form validation."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": self.old_password,
                "new_password": self.new_password,
                "confirm_password": "CompletelyDifferentPassword123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("do not match" in msg.lower() for msg in messages))

    def test_wrong_current_password_attempts_throttled_in_db(self):
        """5 wrong attempts lock password change in DB for 15 minutes, doubling per attempt."""
        # 4 wrong attempts
        for i in range(1, 5):
            resp = self.client.post(
                reverse("account_settings"),
                {
                    "action": "change_password_normal",
                    "current_password": get_test_password(),
                    "new_password": self.new_password,
                    "confirm_password": self.new_password,
                },
                follow=True,
            )
            self.assertEqual(resp.status_code, 200)
            messages = [m.message for m in resp.context["messages"]]
            self.assertTrue(any("remaining" in msg.lower() for msg in messages))

        # 5th wrong attempt triggers 15-minute lockout
        resp_5 = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": get_test_password(),
                "new_password": self.new_password,
                "confirm_password": self.new_password,
            },
            follow=True,
        )
        messages_5 = [m.message for m in resp_5.context["messages"]]
        self.assertTrue(any("locked" in msg.lower() for msg in messages_5))

        # Assert in database ActionThrottle
        throttle = ActionThrottle.objects.get(user=self.user, action=PASSWORD_THROTTLE_ACTION)
        self.assertEqual(throttle.failed_attempts, 5)
        self.assertTrue(throttle.is_locked)
        self.assertIsNotNone(throttle.locked_until)

        # Even with correct password, request is blocked while locked
        locked_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": self.old_password,
                "new_password": self.new_password,
                "confirm_password": self.new_password,
            },
            follow=True,
        )
        messages_locked = [m.message for m in locked_resp.context["messages"]]
        self.assertTrue(any("locked" in msg.lower() for msg in messages_locked))

        # Verify throttle persists in a completely separate Client session (DB backed)
        second_client = Client()
        second_client.login(username="vaultkeeper", password=self.old_password)
        second_resp = second_client.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": self.old_password,
                "new_password": self.new_password,
                "confirm_password": self.new_password,
            },
            follow=True,
        )
        second_messages = [m.message for m in second_resp.context["messages"]]
        self.assertTrue(any("locked" in msg.lower() for msg in second_messages))

    def test_current_session_stays_logged_in_and_other_session_invalidated(self):
        """Current session remains active via update_session_auth_hash while other sessions are logged out."""
        # Client 1 (active browser session)
        client1 = Client()
        client1.login(username="vaultkeeper", password=self.old_password)

        # Client 2 (second active device/session)
        client2 = Client()
        client2.login(username="vaultkeeper", password=self.old_password)

        # Both clients are initially authenticated
        self.assertEqual(client1.get(reverse("account_settings")).status_code, 200)
        self.assertEqual(client2.get(reverse("account_settings")).status_code, 200)

        # Client 1 changes password
        change_resp = client1.post(
            reverse("account_settings"),
            {
                "action": "change_password_normal",
                "current_password": self.old_password,
                "new_password": self.new_password,
                "confirm_password": self.new_password,
            },
            follow=True,
        )
        self.assertEqual(change_resp.status_code, 200)

        # Client 1 remains logged in (update_session_auth_hash called)
        check_client1 = client1.get(reverse("account_settings"))
        self.assertEqual(check_client1.status_code, 200)

        # Client 2 is invalidated and redirected to login
        check_client2 = client2.get(reverse("account_settings"))
        self.assertEqual(check_client2.status_code, 302)
        self.assertIn("/login", check_client2.url)

    def test_forgot_password_path_blocked_without_verified_email(self):
        """Admin or user without verified email cannot use OTP password reset."""
        User.objects.create_superuser(
            username="rawadmin",
            email="",
            password="AdminPassword123!",
        )
        admin_client = Client()
        admin_client.login(username="rawadmin", password="AdminPassword123!")

        response = admin_client.post(
            reverse("account_settings"),
            {"action": "request_password_otp"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("must be added and verified" in msg.lower() for msg in messages))
        self.assertEqual(len(mail.outbox), 0)

    def test_forgot_password_path_success_with_verified_email(self):
        """User with verified email completes OTP reset flow and sets new password."""
        # 1. Request reset OTP
        req_resp = self.client.post(
            reverse("account_settings"),
            {"action": "request_password_otp"},
            follow=True,
        )
        self.assertEqual(req_resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Password Reset Verification Code", mail.outbox[0].subject)

        # Extract 6-digit OTP code
        raw_code = [w for w in mail.outbox[0].body.split() if w.isdigit() and len(w) == 6][0]

        # 2. Confirm OTP code
        confirm_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "verify_password_otp",
                "code": raw_code,
            },
            follow=True,
        )
        self.assertEqual(confirm_resp.status_code, 200)
        self.assertTrue(confirm_resp.context["is_reset_authorized"])

        # 3. Set new password via session window
        set_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "set_password_after_otp",
                "new_password": self.new_password,
                "confirm_password": self.new_password,
            },
            follow=True,
        )
        self.assertEqual(set_resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

        # Verify AccountEvent logged
        event = AccountEvent.objects.filter(
            user=self.user,
            event_type=AccountEvent.EventType.PASSWORD_CHANGED,
        ).first()
        self.assertEqual(event.metadata.get("method"), "email_otp")

    def test_forgot_password_10_minute_window_expiry(self):
        """Authorized OTP session window expires after 10 minutes."""
        # Authorize session with fake timestamp 11 minutes in past
        session = self.client.session
        expired_time = timezone.now() - timedelta(minutes=11)
        session[PASSWORD_RESET_SESSION_KEY] = expired_time.isoformat()
        session.save()

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "set_password_after_otp",
                "new_password": self.new_password,
                "confirm_password": self.new_password,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("expired" in msg.lower() for msg in messages))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_no_password_or_otp_in_logs_or_account_event_metadata(self):
        """Strict privacy guard: passwords and OTPs are never recorded in logs or audit metadata."""
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logging.getLogger("accounts").addHandler(handler)
        logging.getLogger().addHandler(handler)

        secret_probe_pass = get_test_password()

        try:
            # 1. Execute password change normal
            self.client.post(
                reverse("account_settings"),
                {
                    "action": "change_password_normal",
                    "current_password": self.old_password,
                    "new_password": secret_probe_pass,
                    "confirm_password": secret_probe_pass,
                },
            )

            # 2. Execute password reset OTP request
            self.client.post(
                reverse("account_settings"),
                {"action": "request_password_otp"},
            )

            raw_otp = [w for w in mail.outbox[-1].body.split() if w.isdigit() and len(w) == 6][0]

            captured_logs = log_capture.getvalue()

            # Assert password NEVER in logs
            self.assertNotIn(secret_probe_pass, captured_logs)
            self.assertNotIn(self.old_password, captured_logs)
            # Assert OTP NEVER in logs
            self.assertNotIn(raw_otp, captured_logs)

            # Assert AccountEvent metadata contains zero credentials
            events = AccountEvent.objects.filter(user=self.user)
            for ev in events:
                metadata_str = str(ev.metadata)
                self.assertNotIn(secret_probe_pass, metadata_str)
                self.assertNotIn(self.old_password, metadata_str)
                self.assertNotIn(raw_otp, metadata_str)

        finally:
            logging.getLogger("accounts").removeHandler(handler)
            logging.getLogger().removeHandler(handler)
