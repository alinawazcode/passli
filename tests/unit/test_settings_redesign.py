"""
Unit and integration tests for Account Settings redesign:
- Section switching & progressive enhancement (no-JS renders all sections stacked and accessible).
- Legacy anchor mapping targets (#profile, #username, #email, #password).
- Server-driven state preservation (open panel on validation errors, pending email, or reset OTP).
- Zero inline styles and SVG sprite iconography integrity.
- Preservation of all 13 security/form actions and critical test element IDs.
"""

from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    UserProfile,
    PendingEmailChange,
    EmailVerificationCode,
    ActionThrottle,
    AccountEvent,
)
from accounts.services.password_service import PASSWORD_RESET_SESSION_KEY
from tests.unit import get_test_password

User = get_user_model()


class TestSettingsRedesignPhase1(TestCase):
    """Test suite for Phase 1: Section layout, progressive enhancement, and hash mapping targets."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="redesign_tester",
            email="tester@passli.dev",
            password=self.password,
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.is_email_verified = True
        self.profile.display_name = "Redesign Tester"
        self.profile.save()
        self.client.force_login(self.user)
        self.url = reverse("account_settings")

    def test_progressive_enhancement_no_js_renders_all_sections_and_panels(self):
        """Without JavaScript, all three sections (profile, security, activity) and panels are in the DOM without inline display:none."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # 1. Three core sections must be present
        self.assertIn('id="profile"', content)
        self.assertIn('id="security"', content)
        self.assertIn('id="activity"', content)

        # 2. Both desktop menu and mobile pill tab bar must exist
        self.assertIn('class="settings-menu"', content)
        self.assertIn('class="settings-tab-bar"', content)

        # 3. SVG sprite icons must be referenced
        self.assertIn("settings-sprite.svg#icon-", content)

        # 4. Zero inline style="display:none" on sections or cards
        self.assertNotIn('style="display: none;"', content)
        self.assertNotIn('style="display:none"', content)

    def test_legacy_anchor_targets_and_disclosure_ids_exist(self):
        """Legacy redirect targets (#profile, #username, #email, #password) must exist for JS router mapping."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Core section anchors
        self.assertIn('id="profile"', content)
        self.assertIn('id="security"', content)
        self.assertIn('id="activity"', content)

        # Legacy anchor / disclosure targets
        self.assertIn('id="row-username"', content)
        self.assertIn('id="panel-username"', content)
        self.assertIn('id="row-email"', content)
        self.assertIn('id="panel-email"', content)
        self.assertIn('id="row-password"', content)
        self.assertIn('id="panel-password"', content)

    def test_server_state_auto_opens_pending_email_panel(self):
        """When an email change is pending, the email panel is marked for auto-opening on load."""
        PendingEmailChange.objects.create(user=self.user, new_email="newdest@passli.dev")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Email panel should indicate server-open state
        self.assertIn('id="panel-email"', content)
        self.assertIn('data-server-open="true"', content)
        self.assertIn("newdest@passli.dev", content)

    def test_server_state_auto_opens_pending_password_otp_panel(self):
        """When a password reset OTP is pending, the password panel is marked for auto-opening."""
        session = self.client.session
        session["pwd_reset_otp_requested"] = True
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn('id="panel-password"', content)
        self.assertIn('data-server-open="true"', content)
        self.assertIn("form-confirm-password-otp", content)

    def test_server_state_auto_opens_authorized_password_reset_panel(self):
        """When user is in the 10-minute authorized reset window, the password panel is open."""
        session = self.client.session
        session[PASSWORD_RESET_SESSION_KEY] = timezone.now().isoformat()
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn('id="panel-password"', content)
        self.assertIn('data-server-open="true"', content)
        self.assertIn("form-set-password-after-otp", content)


class TestSettingsFeatureParity(TestCase):
    """
    Parity contract enforcement: Assert that every row in the feature parity
    contract exists across its respective server states, including all 13 POST actions
    and all mandatory test element IDs.
    """

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="parity_user",
            email="parity@passli.dev",
            password=self.password,
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.is_email_verified = True
        self.profile.display_name = "Parity User"
        self.profile.save()
        self.client.force_login(self.user)
        self.url = reverse("account_settings")

    def test_all_thirteen_actions_contract(self):
        """Verify the exact presence of all 13 POST actions in their appropriate states."""
        # -------------------------------------------------------------
        # STATE A: Default State (Avatar, Profile, Username, Email Normal, Password Normal, Activity)
        # -------------------------------------------------------------
        # 1. Setup avatar
        self.profile.avatar_path = "avatars/test.webp"
        self.profile.save()

        # Add 3 activity events
        for i in range(3):
            AccountEvent.objects.create(
                user=self.user,
                event_type=AccountEvent.EventType.PASSWORD_CHANGED,
                ip_address="192.168.1.50",
                user_agent="TestBrowser/1.0",
            )

        resp_default = self.client.get(self.url)
        content_default = resp_default.content.decode("utf-8")

        # Action 1: upload_avatar
        self.assertIn('value="upload_avatar"', content_default)
        self.assertIn('id="avatar-file-input"', content_default)
        self.assertIn('id="btn-choose-avatar"', content_default)

        # Action 2: remove_avatar (present when avatar exists)
        self.assertIn('value="remove_avatar"', content_default)
        self.assertIn('id="btn-remove-avatar"', content_default)
        self.assertIn('id="remove-avatar-dialog"', content_default)

        # Action 3: update_profile
        self.assertIn('value="update_profile"', content_default)
        self.assertIn('id="btn-save-profile"', content_default)
        self.assertIn('id="profile-display-name"', content_default)

        # Action 4: change_username (eligible when cooldown is false)
        self.assertIn('value="change_username"', content_default)
        self.assertIn('id="btn-submit-username"', content_default)
        self.assertIn('id="settings-new-username"', content_default)
        self.assertIn('id="settings-username-password"', content_default)

        # Action 5: request_email_change (when no pending email change)
        self.assertIn('value="request_email_change"', content_default)
        self.assertIn('id="btn-request-email-change"', content_default)
        self.assertIn('id="settings-new-email"', content_default)
        self.assertIn('id="settings-email-password"', content_default)

        # Action 9: change_password_normal (normal password state)
        self.assertIn('value="change_password_normal"', content_default)
        self.assertIn('id="btn-submit-password-change"', content_default)
        self.assertIn('id="settings-current-password"', content_default)
        self.assertIn('id="settings-new-password"', content_default)
        self.assertIn('id="settings-confirm-password"', content_default)

        # Action 10: request_password_otp (recovery path when email is verified)
        self.assertIn('value="request_password_otp"', content_default)
        self.assertIn('id="btn-forgot-password-otp"', content_default)

        # Activity table check
        self.assertIn('class="settings-activity-table"', content_default)
        self.assertIn("192.168.1.50", content_default)

        # -------------------------------------------------------------
        # STATE B: Pending Email Change Flow
        # -------------------------------------------------------------
        PendingEmailChange.objects.create(user=self.user, new_email="target_address@passli.dev")
        resp_pending_email = self.client.get(self.url)
        content_email = resp_pending_email.content.decode("utf-8")

        # Action 6: confirm_email_change
        self.assertIn('value="confirm_email_change"', content_email)
        self.assertIn('id="btn-submit-email-otp"', content_email)
        self.assertIn('id="email-otp-combined-input"', content_email)
        self.assertIn('id="email-otp-boxes-container"', content_email)

        # Action 7: resend_email_change_otp
        self.assertIn('value="resend_email_change_otp"', content_email)
        self.assertIn('id="btn-resend-email-otp"', content_email)

        # Action 8: cancel_email_change
        self.assertIn('value="cancel_email_change"', content_email)
        self.assertIn('id="form-cancel-email-change"', content_email)

        # -------------------------------------------------------------
        # STATE C: Pending Password Reset OTP Flow
        # -------------------------------------------------------------
        session = self.client.session
        session["pwd_reset_otp_requested"] = True
        session.save()

        resp_pwd_otp = self.client.get(self.url)
        content_pwd_otp = resp_pwd_otp.content.decode("utf-8")

        # Action 11: verify_password_otp
        self.assertIn('value="verify_password_otp"', content_pwd_otp)
        self.assertIn('id="btn-submit-pwd-otp"', content_pwd_otp)
        self.assertIn('id="password-otp-combined-input"', content_pwd_otp)
        self.assertIn('id="password-otp-boxes-container"', content_pwd_otp)

        # Resend password OTP (uses request_password_otp action)
        self.assertIn('value="request_password_otp"', content_pwd_otp)
        self.assertIn('id="btn-resend-password-otp"', content_pwd_otp)

        # Action 13: cancel_password_reset
        self.assertIn('value="cancel_password_reset"', content_pwd_otp)

        # -------------------------------------------------------------
        # STATE D: Authorized Password Reset Flow (10-minute window)
        # -------------------------------------------------------------
        session["pwd_reset_otp_requested"] = False
        session[PASSWORD_RESET_SESSION_KEY] = timezone.now().isoformat()
        session.save()

        resp_auth = self.client.get(self.url)
        content_auth = resp_auth.content.decode("utf-8")

        # Action 12: set_password_after_otp
        self.assertIn('value="set_password_after_otp"', content_auth)
        self.assertIn('id="btn-submit-otp-new-password"', content_auth)
        self.assertIn('id="settings-otp-new-password"', content_auth)
        self.assertIn('id="settings-otp-confirm-password"', content_auth)

        # Action 13 also available in authorized reset
        self.assertIn('value="cancel_password_reset"', content_auth)

    def test_cooldown_username_state_hides_form_and_renders_cooldown_badge(self):
        """When username is in cooldown, change button is replaced by cooldown message."""
        self.profile.username_changed_at = timezone.now() - timedelta(days=5)
        self.profile.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("COOLDOWN ACTIVE", content)
        self.assertIn("You can change your username again on", content)
        # Button to toggle username change should NOT exist
        self.assertNotIn('id="btn-toggle-username"', content)

    def test_password_locked_state_hides_form_and_renders_locked_notice(self):
        """When password change is throttled, change button is replaced by lock notice."""
        ActionThrottle.objects.create(
            user=self.user,
            action="password_change",
            failed_attempts=5,
            locked_until=timezone.now() + timedelta(minutes=15),
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("Password change is locked", content)
        self.assertNotIn('id="btn-toggle-password"', content)

    def test_empty_activity_renders_empty_state_cleanly(self):
        """When no activity events exist, empty state is displayed."""
        AccountEvent.objects.filter(user=self.user).delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("No recent account activity recorded yet.", content)
