"""
Unit tests for Account Settings Phase 3: Email Change Workflow.
Verifies anti-enumeration, dual notifications, OTP purpose-scoping,
database-backed rate limits/cooldowns, and atomic collision handling.
"""

from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from accounts.models import (
    UserProfile,
    EmailVerificationCode,
    PendingEmailChange,
    AccountEvent,
)
from accounts.services.otp_service import issue_otp
from tests.unit import get_test_password

User = get_user_model()


class EmailChangeWorkflowTests(TestCase):
    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="testuser",
            email="primary@example.com",
            password=self.password,
        )
        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={"is_email_verified": True},
        )
        self.profile.is_email_verified = True
        self.profile.save()

        self.other_user = User.objects.create_user(
            username="otheruser",
            email="existing@example.com",
            password=self.password,
        )

        self.client.login(username="testuser", password=self.password)

    def test_user_email_unchanged_until_otp_confirmed(self):
        """User email remains primary@example.com until OTP is confirmed."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "brandnew@example.com",
                "current_password": self.password,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # 1. Assert user.email is unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "primary@example.com")

        # 2. Assert pending record exists
        pending = PendingEmailChange.objects.filter(user=self.user).first()
        self.assertIsNotNone(pending)
        self.assertEqual(pending.new_email, "brandnew@example.com")

        # 3. Retrieve raw OTP from verification code record
        otp_record = EmailVerificationCode.objects.filter(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
            is_used=False,
        ).first()
        self.assertIsNotNone(otp_record)

        # Find the OTP code in outgoing mail
        self.assertEqual(len(mail.outbox), 2)  # 1 to new_email, 1 notice to old_email
        new_mail = [m for m in mail.outbox if "brandnew@example.com" in m.to][0]
        # Extract 6-digit code from email body
        raw_code = None
        for word in new_mail.body.split():
            if word.isdigit() and len(word) == 6:
                raw_code = word
                break
        self.assertIsNotNone(raw_code)

        # 4. Confirm with wrong code -> still unchanged
        fail_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "confirm_email_change",
                "code": "000000",
            },
            follow=True,
        )
        self.assertEqual(fail_resp.status_code, 200)
        self.assertTrue(any("invalid" in m.message.lower() for m in fail_resp.context["messages"]))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "primary@example.com")

        # 5. Confirm with valid code -> email updated & verified
        success_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "confirm_email_change",
                "code": raw_code,
            },
            follow=True,
        )
        self.assertEqual(success_resp.status_code, 200)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.email, "brandnew@example.com")
        self.assertTrue(self.profile.is_email_verified)
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_otp_goes_to_new_address_only(self):
        """OTP code is delivered exclusively to the new address."""
        self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "target@example.com",
                "current_password": self.password,
            },
        )
        self.assertEqual(len(mail.outbox), 2)
        new_email_msg = [m for m in mail.outbox if "target@example.com" in m.to][0]
        old_email_msg = [m for m in mail.outbox if "primary@example.com" in m.to][0]

        # New email contains the verification code
        self.assertIn("Verify Your New Email Address", new_email_msg.subject)
        # Old email is a security advisory without the OTP code
        self.assertIn("Security Alert", old_email_msg.subject)
        self.assertNotIn("Verify Your New Email Address", old_email_msg.subject)

    def test_old_address_gets_notices_on_request_and_completion(self):
        """Old address receives security alert on request and final confirmation on completion."""
        # 1. Request change
        self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "forward@example.com",
                "current_password": self.password,
            },
        )
        self.assertEqual(len(mail.outbox), 2)
        alert_msg = [m for m in mail.outbox if "primary@example.com" in m.to][0]
        self.assertIn("Security Alert: Email Change Requested", alert_msg.subject)

        # Retrieve OTP code
        new_msg = [m for m in mail.outbox if "forward@example.com" in m.to][0]
        raw_code = [w for w in new_msg.body.split() if w.isdigit() and len(w) == 6][0]

        mail.outbox.clear()

        # 2. Confirm change
        self.client.post(
            reverse("account_settings"),
            {
                "action": "confirm_email_change",
                "code": raw_code,
            },
        )
        self.assertEqual(len(mail.outbox), 2)
        confirmed_old_msg = [m for m in mail.outbox if "primary@example.com" in m.to][0]
        self.assertIn("Security Confirmation: Passli Account Email Address Changed", confirmed_old_msg.subject)

        new_confirmed_msg = [m for m in mail.outbox if "forward@example.com" in m.to][0]
        self.assertIn("Email Address Verified Successfully", new_confirmed_msg.subject)

    def test_admin_with_empty_email_can_add_and_verify(self):
        """Admins and users without an email on file can add and verify one smoothly."""
        admin_user = User.objects.create_superuser(
            username="passliadmin",
            email="",
            password="AdminPassword123!",
        )
        self.client.login(username="passliadmin", password="AdminPassword123!")

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "admin@passli.org",
                "current_password": "AdminPassword123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Only 1 email sent (to admin@passli.org) because there was no prior old email
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("admin@passli.org", mail.outbox[0].to)

        raw_code = [w for w in mail.outbox[0].body.split() if w.isdigit() and len(w) == 6][0]

        # Confirm
        confirm_resp = self.client.post(
            reverse("account_settings"),
            {
                "action": "confirm_email_change",
                "code": raw_code,
            },
            follow=True,
        )
        self.assertEqual(confirm_resp.status_code, 200)
        admin_user.refresh_from_db()
        self.assertEqual(admin_user.email, "admin@passli.org")
        admin_profile = UserProfile.objects.get(user=admin_user)
        self.assertTrue(admin_profile.is_email_verified)

    def test_identical_response_for_taken_and_free_addresses(self):
        """Anti-enumeration: taken address and free address produce identical response."""
        # 1. Request existing taken address
        resp_taken = self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "existing@example.com",
                "current_password": self.password,
            },
            follow=True,
        )
        self.assertEqual(resp_taken.status_code, 200)
        messages_taken = [m.message for m in resp_taken.context["messages"]]
        self.assertIn("If this address can be used, a verification code has been sent.", messages_taken)
        # No email sent to taken address or user
        self.assertEqual(len(mail.outbox), 0)

        # 2. Request fresh available address
        resp_free = self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "fresh@example.com",
                "current_password": self.password,
            },
            follow=True,
        )
        self.assertEqual(resp_free.status_code, 200)
        messages_free = [m.message for m in resp_free.context["messages"]]
        self.assertIn("If this address can be used, a verification code has been sent.", messages_free)
        # Outgoing OTP email was sent
        self.assertGreater(len(mail.outbox), 0)

    def test_rejection_of_expired_code(self):
        """Codes older than 15 minutes are rejected and email remains unchanged."""
        self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "expirytest@example.com",
                "current_password": self.password,
            },
        )
        otp_record = EmailVerificationCode.objects.filter(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
        ).first()

        # Fast forward expiration to 1 minute in the past
        otp_record.expires_at = timezone.now() - timedelta(minutes=1)
        otp_record.save()

        raw_code = [w for w in mail.outbox[0].body.split() if w.isdigit() and len(w) == 6][0]

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "confirm_email_change",
                "code": raw_code,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "primary@example.com")
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("expired" in msg.lower() for msg in messages))

    def test_rejection_of_locked_code_after_5_attempts(self):
        """Code is permanently locked after 5 failed submission attempts."""
        self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "lockout@example.com",
                "current_password": self.password,
            },
        )
        raw_code = [w for w in mail.outbox[0].body.split() if w.isdigit() and len(w) == 6][0]

        # 5 wrong attempts
        for _ in range(5):
            self.client.post(
                reverse("account_settings"),
                {"action": "confirm_email_change", "code": "111111"},
            )

        # 6th attempt with CORRECT code is rejected because code is locked
        response = self.client.post(
            reverse("account_settings"),
            {"action": "confirm_email_change", "code": raw_code},
            follow=True,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "primary@example.com")
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("exceeded" in msg.lower() or "locked" in msg.lower() for msg in messages))

    def test_rejection_of_reused_code(self):
        """A code that has already been verified cannot be used again."""
        self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "reusetest@example.com",
                "current_password": self.password,
            },
        )
        raw_code = [w for w in mail.outbox[0].body.split() if w.isdigit() and len(w) == 6][0]

        # First use -> success
        self.client.post(
            reverse("account_settings"),
            {"action": "confirm_email_change", "code": raw_code},
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "reusetest@example.com")

        # Second attempt to use code -> fails
        response = self.client.post(
            reverse("account_settings"),
            {"action": "confirm_email_change", "code": raw_code},
            follow=True,
        )
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("invalid" in msg.lower() or "no pending" in msg.lower() for msg in messages))

    def test_cross_purpose_code_isolation(self):
        """Codes issued for verify_email cannot be used for change_email."""
        PendingEmailChange.objects.create(user=self.user, new_email="spoofed@example.com")
        _, verify_otp_code = issue_otp(
            user=self.user,
            email="spoofed@example.com",
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        )

        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "confirm_email_change",
                "code": verify_otp_code,
            },
            follow=True,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "primary@example.com")
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("invalid" in msg.lower() or "expired" in msg.lower() for msg in messages))

    def test_race_condition_taken_email_between_request_and_confirm(self):
        """If another user claims the pending address before confirmation, abort gracefully."""
        self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "race@example.com",
                "current_password": self.password,
            },
        )
        raw_code = [w for w in mail.outbox[0].body.split() if w.isdigit() and len(w) == 6][0]

        # Another user registers or claims race@example.com
        User.objects.create_user(
            username="racer",
            email="race@example.com",
            password=get_test_password(),
        )

        # Now testuser attempts to confirm
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "confirm_email_change",
                "code": raw_code,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "primary@example.com")
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("no longer available" in msg.lower() for msg in messages))

    def test_cancel_pending_email_change(self):
        """User can cancel an active pending email change request."""
        self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "cancelme@example.com",
                "current_password": self.password,
            },
        )
        self.assertTrue(PendingEmailChange.objects.filter(user=self.user).exists())

        cancel_resp = self.client.post(
            reverse("account_settings"),
            {"action": "cancel_email_change"},
            follow=True,
        )
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "primary@example.com")

    def test_wrong_password_on_email_change_request(self):
        """Entering incorrect current password aborts request and logs reauth_failed event."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "request_email_change",
                "new_email": "badpass@example.com",
                "current_password": get_test_password(),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())
        self.assertTrue(
            AccountEvent.objects.filter(
                user=self.user,
                event_type=AccountEvent.EventType.REAUTH_FAILED,
            ).exists()
        )
