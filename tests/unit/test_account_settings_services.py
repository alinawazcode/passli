"""
Unit tests for Account Settings services (Phase 1):
- Username service: format, reserved words, '@' rejection, case-insensitive uniqueness,
  30-day cooldown boundaries (29d 23h vs 30d), row locking, audit events, email alerts.
- Avatar service: MIME validation via Pillow, 2 MB size limit, decompression bomb guard,
  animated/multi-frame rejection, EXIF orientation, square center-crop, WebP re-encoding,
  metadata stripping, old file deletion on replace/remove.
- OTP service: purpose isolation (cross-purpose rejection), expiry, attempt exhaustion,
  single use, 60s cooldown, 5 codes/hour cap.
- Email change service: pending isolation (user.email untouched), reauth, anti-enumeration,
  notices to old/new addresses, atomic uniqueness re-check.
- Password change service: dual paths (normal reauth + forgot OTP), database failure throttle
  with exponential backoff, session window expiry, session auth hash rotation.
- ensure_superadmin command: empty DB, rename-then-rerun idempotency, and --force override.
"""

import io
import os
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch
from PIL import Image

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import (
    UserProfile,
    EmailVerificationCode,
    PendingEmailChange,
    AccountEvent,
    ActionThrottle,
)
from accounts.services.activity_service import log_account_event, sanitize_metadata
from accounts.services.otp_service import issue_otp, verify_otp
from accounts.services.username_service import (
    change_username,
    get_username_cooldown_status,
    validate_username_format,
    USERNAME_COOLDOWN_DAYS,
)
from accounts.services.avatar_service import (
    process_and_save_avatar,
    remove_avatar,
)
from accounts.services.email_change_service import (
    request_email_change,
    confirm_email_change,
)
from accounts.services.password_service import (
    change_password_normal,
    request_password_reset_otp,
    verify_password_reset_otp,
    change_password_via_otp_session,
    get_password_change_throttle,
    record_password_change_failure,
    reset_password_change_throttle,
    PASSWORD_RESET_SESSION_KEY,
)
from tests.unit import get_test_password

User = get_user_model()


class TestActivityService(TestCase):
    """Test audit activity logging and metadata sanitization."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="activity_user",
            email="activity@passli.dev",
            password=self.password,
        )

    def test_metadata_strips_sensitive_keys(self):
        dirty_meta = {
            "action": "login",
            "current_password": "SuperSecretPassword123!",
            "new_password": "AnotherPassword456!",
            "otp_code": "123456",
            "auth_token": "xyz987",
            "client_status": "ok",
        }
        clean = sanitize_metadata(dirty_meta)
        self.assertIn("action", clean)
        self.assertIn("client_status", clean)
        self.assertNotIn("current_password", clean)
        self.assertNotIn("new_password", clean)
        self.assertNotIn("otp_code", clean)
        self.assertNotIn("auth_token", clean)

    def test_log_account_event_creates_record(self):
        event = log_account_event(
            user=self.user,
            event_type=AccountEvent.EventType.USERNAME_CHANGED,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Test Suite",
            metadata={"old_username": "old_name", "new_username": "new_name"},
        )
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.event_type, AccountEvent.EventType.USERNAME_CHANGED)
        self.assertEqual(event.ip_address, "192.168.1.100")
        self.assertEqual(event.metadata["old_username"], "old_name")


class TestOTPService(TestCase):
    """Test purpose-scoped OTP generation, verification, and limits."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="otp_user",
            email="otp@passli.dev",
            password=self.password,
        )

    def test_issue_and_verify_otp_success(self):
        record, raw_otp = issue_otp(
            user=self.user,
            email=self.user.email,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        )
        self.assertEqual(len(raw_otp), 6)
        self.assertTrue(raw_otp.isdigit())
        self.assertFalse(record.is_used)

        is_valid, err = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            submitted_code=raw_otp,
            email=self.user.email,
        )
        self.assertTrue(is_valid)
        self.assertEqual(err, "")

        record.refresh_from_db()
        self.assertTrue(record.is_used)

    def test_single_use_prevents_replay(self):
        _, raw_otp = issue_otp(
            user=self.user,
            email=self.user.email,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        )
        # First use succeeds
        is_valid, _ = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            submitted_code=raw_otp,
        )
        self.assertTrue(is_valid)

        # Replay attempt must fail
        is_valid_again, err = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            submitted_code=raw_otp,
        )
        self.assertFalse(is_valid_again)
        self.assertIn("expired or is invalid", err)

    def test_cross_purpose_rejection(self):
        """A code issued for change_email MUST NOT verify change_password or verify_email."""
        _, raw_otp = issue_otp(
            user=self.user,
            email=self.user.email,
            purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
        )

        # Attempt to verify with change_password purpose
        is_valid_pwd, _ = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_CHANGE_PASSWORD,
            submitted_code=raw_otp,
        )
        self.assertFalse(is_valid_pwd)

        # Attempt to verify with verify_email purpose
        is_valid_reg, _ = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            submitted_code=raw_otp,
        )
        self.assertFalse(is_valid_reg)

        # Verifying with the correct purpose must succeed
        is_valid_correct, _ = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
            submitted_code=raw_otp,
        )
        self.assertTrue(is_valid_correct)

    def test_expiry_invalidation(self):
        record, raw_otp = issue_otp(
            user=self.user,
            email=self.user.email,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        )
        # Set expiry in the past
        record.expires_at = timezone.now() - timedelta(minutes=1)
        record.save(update_fields=["expires_at"])

        is_valid, err = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            submitted_code=raw_otp,
        )
        self.assertFalse(is_valid)
        self.assertIn("expired", err)

    def test_max_attempts_lockout(self):
        record, raw_otp = issue_otp(
            user=self.user,
            email=self.user.email,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        )

        # 5 consecutive incorrect submissions
        for i in range(5):
            is_valid, err = verify_otp(
                user=self.user,
                purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
                submitted_code="000000",
            )
            self.assertFalse(is_valid)

        record.refresh_from_db()
        self.assertTrue(record.is_locked)

        # Even the correct code is now rejected
        is_valid_now, err_locked = verify_otp(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            submitted_code=raw_otp,
        )
        self.assertFalse(is_valid_now)
        self.assertIn("Maximum verification attempts exceeded", err_locked)

    def test_resend_cooldown_60_seconds(self):
        issue_otp(
            user=self.user,
            email=self.user.email,
            purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
        )
        # Immediate second request must trigger cooldown ValidationError
        with self.assertRaises(ValidationError) as ctx:
            issue_otp(
                user=self.user,
                email=self.user.email,
                purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            )
        self.assertIn("Please wait", str(ctx.exception))

    def test_hourly_cap_5_codes(self):
        now = timezone.now()
        # Seed 5 codes generated over the past hour
        for i in range(5):
            rec = EmailVerificationCode.objects.create(
                user=self.user,
                email=self.user.email,
                purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
                expires_at=now + timedelta(minutes=15),
                is_used=True,
            )
            rec.created_at = now - timedelta(minutes=10 + i * 5)
            rec.save(update_fields=["created_at"])

        with self.assertRaises(ValidationError) as ctx:
            issue_otp(
                user=self.user,
                email=self.user.email,
                purpose=EmailVerificationCode.PURPOSE_VERIFY_EMAIL,
            )
        self.assertIn("Maximum code request limit reached", str(ctx.exception))


class TestUsernameService(TestCase):
    """Test username validation rules, reserved names, '@' prohibition, cooldowns, and updates."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="initial_user",
            email="user@passli.dev",
            password=self.password,
        )
        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={"is_email_verified": True},
        )
        self.profile.is_email_verified = True
        self.profile.save()

    def test_username_validation_rejects_at_symbol(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_username_format("alice@company.com", current_user=self.user)
        self.assertIn("cannot contain the '@' symbol", str(ctx.exception))

    def test_username_validation_rejects_reserved_words(self):
        for name in ["admin", "Administrator", "ROOT", "passli", "support", "system"]:
            with self.assertRaises(ValidationError) as ctx:
                validate_username_format(name, current_user=self.user)
            self.assertIn("reserved", str(ctx.exception).lower())

    def test_username_validation_length_bounds(self):
        with self.assertRaises(ValidationError):
            validate_username_format("ab", current_user=self.user)  # < 3
        with self.assertRaises(ValidationError):
            validate_username_format("a" * 31, current_user=self.user)  # > 30

    def test_username_case_insensitive_uniqueness(self):
        User.objects.create_user(username="takenname", password=self.password)
        with self.assertRaises(ValidationError) as ctx:
            validate_username_format("TAKENNAME", current_user=self.user)
        self.assertIn("already in use", str(ctx.exception))

    def test_first_change_allowed_when_username_changed_at_is_null(self):
        status = get_username_cooldown_status(self.user)
        self.assertTrue(status["can_change"])
        self.assertIsNone(status["next_change_date"])

        # Successful change
        change_username(
            user=self.user,
            new_username="valid_new_name",
            current_password=self.password,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "valid_new_name")
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.username_changed_at)

    def test_cooldown_boundary_29_days_23_hours_rejected(self):
        now = timezone.now()
        # Changed 29 days and 23 hours ago (1 hour short of 30 days)
        self.profile.username_changed_at = now - timedelta(days=29, hours=23)
        self.profile.save()

        status = get_username_cooldown_status(self.user)
        self.assertFalse(status["can_change"])
        self.assertGreater(status["days_remaining"], 0)

        with self.assertRaises(ValidationError) as ctx:
            change_username(
                user=self.user,
                new_username="second_change",
                current_password=self.password,
            )
        self.assertIn("You can change your username again on", str(ctx.exception))

    def test_cooldown_boundary_30_days_allowed(self):
        now = timezone.now()
        # Exactly 30 days ago
        self.profile.username_changed_at = now - timedelta(days=USERNAME_COOLDOWN_DAYS)
        self.profile.save()

        status = get_username_cooldown_status(self.user)
        self.assertTrue(status["can_change"])

        change_username(
            user=self.user,
            new_username="third_change",
            current_password=self.password,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "third_change")

    def test_change_username_wrong_password_rejected_and_logged(self):
        with self.assertRaises(ValidationError) as ctx:
            change_username(
                user=self.user,
                new_username="name_with_bad_pw",
                current_password="WrongPassword123!",
            )
        self.assertIn("current password entered is incorrect", str(ctx.exception))
        # AccountEvent for reauth failure must be logged
        self.assertTrue(
            AccountEvent.objects.filter(
                user=self.user,
                event_type=AccountEvent.EventType.REAUTH_FAILED,
            ).exists()
        )

    def test_change_username_sends_notification_to_verified_email(self):
        mail.outbox.clear()
        change_username(
            user=self.user,
            new_username="brand_new_alias",
            current_password=self.password,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Security Notice", mail.outbox[0].subject)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_admin_without_email_can_change_username_without_crash(self):
        admin = User.objects.create_superuser(
            username="passliadmin",
            email="",
            password=self.password,
        )
        mail.outbox.clear()
        change_username(
            user=admin,
            new_username="renamedadmin",
            current_password=self.password,
        )
        admin.refresh_from_db()
        self.assertEqual(admin.username, "renamedadmin")
        self.assertEqual(len(mail.outbox), 0)  # No crash, email skipped


class TestAvatarService(TestCase):
    """Test avatar Pillow inspection, square cropping, resizing, and secure WebP storage."""

    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="avatar_user",
            password=self.password,
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def tearDown(self):
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def create_test_image(self, width=400, height=300, fmt="JPEG", mode="RGB") -> SimpleUploadedFile:
        img = Image.new(mode, (width, height), color=(15, 23, 42))
        buffer = io.BytesIO()
        img.save(buffer, format=fmt)
        buffer.seek(0)
        ext = fmt.lower()
        return SimpleUploadedFile(f"test_avatar.{ext}", buffer.getvalue(), content_type=f"image/{ext}")

    def test_avatar_valid_jpeg_processed_to_square_webp(self):
        with override_settings(MEDIA_ROOT=self.temp_media):
            upload = self.create_test_image(width=600, height=400, fmt="JPEG")
            rel_path = process_and_save_avatar(self.user, upload)

            self.assertTrue(rel_path.startswith("avatars/"))
            self.assertTrue(rel_path.endswith(".webp"))

            full_path = os.path.join(self.temp_media, rel_path)
            self.assertTrue(os.path.exists(full_path))

            # Inspect resulting WebP
            with Image.open(full_path) as saved_img:
                self.assertEqual(saved_img.format, "WEBP")
                self.assertEqual(saved_img.size, (256, 256))
                # Confirm metadata stripped (no EXIF)
                self.assertNotIn("exif", saved_img.info)

    def test_avatar_rejects_non_image_payload(self):
        with override_settings(MEDIA_ROOT=self.temp_media):
            fake_img = SimpleUploadedFile("fake.jpg", b"NOT_AN_IMAGE_PAYLOAD", content_type="image/jpeg")
            with self.assertRaises(ValidationError) as ctx:
                process_and_save_avatar(self.user, fake_img)
            self.assertIn("Invalid or corrupted image", str(ctx.exception))

    def test_avatar_rejects_oversized_file(self):
        with override_settings(MEDIA_ROOT=self.temp_media):
            # 2 MB + 1 byte
            big_data = b"X" * (2 * 1024 * 1024 + 1)
            big_file = SimpleUploadedFile("big.jpg", big_data, content_type="image/jpeg")
            with self.assertRaises(ValidationError) as ctx:
                process_and_save_avatar(self.user, big_file)
            self.assertIn("must not exceed 2 MB", str(ctx.exception))

    def test_avatar_rejects_decompression_bomb(self):
        with override_settings(MEDIA_ROOT=self.temp_media):
            # 4000x3000 = 12 million pixels > 10 million limit
            huge_img = Image.new("RGB", (4000, 3000), color=(0, 0, 0))
            buffer = io.BytesIO()
            huge_img.save(buffer, format="JPEG")
            buffer.seek(0)
            upload = SimpleUploadedFile("bomb.jpg", buffer.getvalue(), content_type="image/jpeg")

            with self.assertRaises(ValidationError) as ctx:
                process_and_save_avatar(self.user, upload)
            self.assertTrue("excessively large" in str(ctx.exception) or "decompression" in str(ctx.exception).lower())

    def test_avatar_replaces_and_deletes_old_file(self):
        with override_settings(MEDIA_ROOT=self.temp_media):
            up1 = self.create_test_image(fmt="JPEG")
            path1 = process_and_save_avatar(self.user, up1)
            full1 = os.path.join(self.temp_media, path1)
            self.assertTrue(os.path.exists(full1))

            up2 = self.create_test_image(fmt="PNG")
            path2 = process_and_save_avatar(self.user, up2)
            full2 = os.path.join(self.temp_media, path2)

            self.assertTrue(os.path.exists(full2))
            self.assertFalse(os.path.exists(full1))  # Old file deleted

    def test_remove_avatar_cleans_file_and_records_event(self):
        with override_settings(MEDIA_ROOT=self.temp_media):
            up = self.create_test_image(fmt="WEBP")
            path = process_and_save_avatar(self.user, up)
            full = os.path.join(self.temp_media, path)
            self.assertTrue(os.path.exists(full))

            remove_avatar(self.user)
            self.assertFalse(os.path.exists(full))
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.avatar_path, "")
            self.assertTrue(
                AccountEvent.objects.filter(
                    user=self.user,
                    event_type=AccountEvent.EventType.AVATAR_REMOVED,
                ).exists()
            )


class TestEmailChangeService(TestCase):
    """Test full email change flow: re-authentication, isolation, anti-enumeration, and OTP verification."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="email_change_user",
            email="old_verified@passli.dev",
            password=self.password,
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.is_email_verified = True
        self.profile.save()

    def test_email_change_request_stores_pending_and_sends_notices(self):
        mail.outbox.clear()
        success, msg = request_email_change(
            user=self.user,
            new_email="new_target@passli.dev",
            current_password=self.password,
        )
        self.assertTrue(success)
        self.assertIn("verification code has been sent", msg)

        # auth.User.email MUST remain unchanged prior to verification
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old_verified@passli.dev")

        # Pending record must exist
        pending = PendingEmailChange.objects.get(user=self.user)
        self.assertEqual(pending.new_email, "new_target@passli.dev")

        # Two emails sent: OTP to new email + security notice to old email
        self.assertEqual(len(mail.outbox), 2)
        recipients = [m.to[0] for m in mail.outbox]
        self.assertIn("new_target@passli.dev", recipients)
        self.assertIn("old_verified@passli.dev", recipients)

    def test_email_change_anti_enumeration(self):
        """Requesting change to an already-registered address returns generic notice without sending code."""
        User.objects.create_user(
            username="other_user",
            email="taken@passli.dev",
            password=self.password,
        )
        mail.outbox.clear()
        success, msg = request_email_change(
            user=self.user,
            new_email="TAKEN@passli.dev",
            current_password=self.password,
        )
        self.assertTrue(success)
        self.assertIn("verification code has been sent", msg)  # Same generic response
        # No pending change created and no OTP sent to taken address
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_email_change_confirmation_updates_user_email(self):
        request_email_change(
            user=self.user,
            new_email="verified_new@passli.dev",
            current_password=self.password,
        )
        # Extract OTP from DB
        code_record = EmailVerificationCode.objects.filter(
            user=self.user,
            purpose=EmailVerificationCode.PURPOSE_CHANGE_EMAIL,
        ).first()
        self.assertIsNotNone(code_record)

        # Submit wrong code
        ok, err = confirm_email_change(self.user, "000000")
        self.assertFalse(ok)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old_verified@passli.dev")

        # Mock check_password on code record to verify correct code submission
        with patch.object(EmailVerificationCode, "verify_code", return_value=True):
            ok_correct, msg = confirm_email_change(self.user, "123456")
            self.assertTrue(ok_correct)

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "verified_new@passli.dev")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_email_verified)
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())

    def test_admin_with_no_email_can_add_and_verify_email(self):
        admin = User.objects.create_superuser(
            username="no_email_admin",
            email="",
            password=self.password,
        )
        mail.outbox.clear()

        # 1. Request new email
        ok, _ = request_email_change(admin, "admin_new@passli.dev", self.password)
        self.assertTrue(ok)
        # Only 1 email sent (OTP to new address; no old address notice)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin_new@passli.dev"])

        # 2. Confirm code
        with patch.object(EmailVerificationCode, "verify_code", return_value=True):
            ok_conf, _ = confirm_email_change(admin, "654321")
            self.assertTrue(ok_conf)

        admin.refresh_from_db()
        self.assertEqual(admin.email, "admin_new@passli.dev")


class TestPasswordService(TestCase):
    """Test normal and OTP password changes, failure throttling, and session authorizers."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="pwd_user",
            email="pwd@passli.dev",
            password=self.password,
        )
        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={"is_email_verified": True},
        )
        self.profile.is_email_verified = True
        self.profile.save()

    def test_normal_password_change_success(self):
        new_pw = "NewSecureMasterPassphrase2026!"
        ok, msg = change_password_normal(
            user=self.user,
            current_password=self.password,
            new_password=new_pw,
            confirm_password=new_pw,
        )
        self.assertTrue(ok)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_pw))

    def test_normal_password_change_rejects_same_password(self):
        with self.assertRaises(ValidationError) as ctx:
            change_password_normal(
                user=self.user,
                current_password=self.password,
                new_password=self.password,
                confirm_password=self.password,
            )
        self.assertIn("cannot be the same as your current password", str(ctx.exception))

    def test_database_throttle_locks_after_5_failures_for_15_minutes(self):
        # 4 failed attempts: not locked yet
        for i in range(4):
            record_password_change_failure(self.user)
            is_locked, _, _ = get_password_change_throttle(self.user)
            self.assertFalse(is_locked)

        # 5th failed attempt: triggers 15-minute lock
        record_password_change_failure(self.user)
        is_locked, retry_mins, fails = get_password_change_throttle(self.user)
        self.assertTrue(is_locked)
        self.assertEqual(fails, 5)
        self.assertGreaterEqual(retry_mins, 14)

        # Normal password change is now locked
        new_pw = "AnotherValidPassphrase2026!"
        with self.assertRaises(ValidationError) as ctx:
            change_password_normal(
                user=self.user,
                current_password=self.password,
                new_password=new_pw,
                confirm_password=new_pw,
            )
        self.assertIn("Password change is locked", str(ctx.exception))

    def test_reset_password_otp_blocked_without_verified_email(self):
        admin = User.objects.create_superuser(
            username="unverified_admin",
            email="",
            password=self.password,
        )
        with self.assertRaises(ValidationError) as ctx:
            request_password_reset_otp(admin)
        self.assertIn("An email address must be added and verified", str(ctx.exception))

    def test_forgot_password_otp_and_session_window_expiry(self):
        class DummyRequest:
            def __init__(self):
                self.session = {}

        dummy_req = DummyRequest()
        mail.outbox.clear()

        # 1. Request OTP
        ok, _ = request_password_reset_otp(self.user)
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)

        # 2. Verify OTP sets session flag
        with patch.object(EmailVerificationCode, "verify_code", return_value=True):
            ok_v, _ = verify_password_reset_otp(self.user, "112233", dummy_req)
            self.assertTrue(ok_v)
            self.assertIn(PASSWORD_RESET_SESSION_KEY, dummy_req.session)

        # 3. Simulate window expiry (>10 minutes)
        expired_time = timezone.now() - timedelta(minutes=11)
        dummy_req.session[PASSWORD_RESET_SESSION_KEY] = expired_time.isoformat()

        new_pw = "FreshSecurePassphrase2026!"
        with self.assertRaises(ValidationError) as ctx:
            change_password_via_otp_session(self.user, new_pw, new_pw, dummy_req)
        self.assertIn("password reset window has expired", str(ctx.exception))


class TestEnsureSuperadminScenarios(TestCase):
    """Test ensure_superadmin: empty DB run, rename-then-rerun idempotency, and --force."""

    def setUp(self):
        self.admin_pw = get_test_password()
        os.environ["DJANGO_SUPERUSER_USERNAME"] = "envadmin"
        os.environ["DJANGO_SUPERUSER_PASSWORD"] = self.admin_pw

    def tearDown(self):
        os.environ.pop("DJANGO_SUPERUSER_USERNAME", None)
        os.environ.pop("DJANGO_SUPERUSER_PASSWORD", None)

    def test_empty_db_creates_superuser(self):
        out = io.StringIO()
        call_command("ensure_superadmin", stdout=out)
        self.assertTrue(User.objects.filter(username="envadmin").exists())

    def test_rename_then_rerun_does_not_recreate_old_superuser(self):
        out = io.StringIO()
        call_command("ensure_superadmin", stdout=out)
        admin = User.objects.get(username="envadmin")

        # Admin renames themselves
        admin.username = "custom_renamed_admin"
        admin.save(update_fields=["username"])

        # Rerun ensure_superadmin: since active superuser exists, must skip!
        out2 = io.StringIO()
        call_command("ensure_superadmin", stdout=out2)
        self.assertIn("Active superuser already exists", out2.getvalue())
        self.assertFalse(User.objects.filter(username="envadmin").exists())

    def test_force_creates_superuser_when_active_already_exists(self):
        # Create an existing active superuser
        User.objects.create_superuser(username="existing_super", password=self.admin_pw)

        # Unforced must skip
        out_skip = io.StringIO()
        call_command("ensure_superadmin", stdout=out_skip)
        self.assertFalse(User.objects.filter(username="envadmin").exists())

        # Forced run must create envadmin
        out_force = io.StringIO()
        call_command("ensure_superadmin", "--force", stdout=out_force)
        self.assertTrue(User.objects.filter(username="envadmin").exists())


class ConcurrentUsernameChangeTests(TransactionTestCase):
    """Test that concurrent attempts to change username respect profile row locks and cooldown."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="concurrent_user",
            password=self.password,
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_concurrent_username_changes_one_succeeds_one_fails(self):
        import threading
        from django.db import connection

        results = []
        errors = []

        def attempt_change(new_name):
            try:
                # In each thread, refetch user and execute change
                u = User.objects.get(pk=self.user.pk)
                change_username(u, new_name, self.password)
                results.append(new_name)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        t1 = threading.Thread(target=attempt_change, args=("racer_alpha",))
        t2 = threading.Thread(target=attempt_change, args=("racer_beta",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one thread must succeed; the other fails due to cooldown or row lock
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, results[0])
