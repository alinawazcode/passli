"""
Unit and integration tests for Account Settings redesign:
- Section switching & progressive enhancement (no-JS renders all sections stacked and accessible).
- Legacy anchor mapping targets (#profile, #username, #email, #password).
- Server-driven state preservation (open panel on validation errors, pending email, or reset OTP).
- Zero inline styles and SVG sprite iconography integrity.
- Preservation of all 13 security/form actions and critical test element IDs.
"""

import re
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
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


class TestSettingsAlertsAndStyles(TestCase):
    """
    Phase 1 Test Suite:
    - Flash messages render exactly once on /settings/ with tag-to-style mapping and ARIA roles.
    - Global messages block in base.html continues to render on other pages.
    - Zero inline style= attributes across all major states.
    - Zero inline event handlers (onclick=, etc.) across all major states.
    """

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="alerts_tester",
            email="alerts@passli.dev",
            password=self.password,
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.is_email_verified = True
        self.profile.display_name = "Alerts Tester"
        self.profile.save()
        self.client.force_login(self.user)
        self.url = reverse("account_settings")

    def test_flash_messages_rendered_once_on_settings_with_roles_and_tags(self):
        """Messages on /settings/ render once in .settings-alerts with correct role and level style."""
        # 1. Integration test: update profile triggers success message followed by redirect
        resp_success = self.client.post(
            self.url,
            {"action": "update_profile", "display_name": "Updated Name"},
            follow=True,
        )
        self.assertEqual(resp_success.status_code, 200)
        content_success = resp_success.content.decode("utf-8")

        # Must appear exactly once
        self.assertEqual(
            content_success.count("Your profile details have been updated."),
            1,
            "Flash message must render exactly once on the settings page, not duplicated.",
        )
        # Must have correct role and style
        self.assertIn('class="settings-alert settings-alert-success"', content_success)
        self.assertIn('role="status"', content_success)
        self.assertIn('data-action="dismiss-alert"', content_success)
        self.assertIn('data-testid="messages-container"', content_success)

        # 2. Integration test: invalid submission triggers error message
        resp_error = self.client.post(
            self.url,
            {"action": "update_profile", "display_name": "A" * 51},  # exceeds max_length 50
            follow=True,
        )
        self.assertEqual(resp_error.status_code, 200)
        content_error = resp_error.content.decode("utf-8")

        self.assertEqual(
            content_error.count("Could not update profile. Please correct the errors below."),
            1,
            "Error flash message must render exactly once.",
        )
        self.assertIn('class="settings-alert settings-alert-danger"', content_error)
        self.assertIn('role="alert"', content_error)

    def test_all_message_tag_styles_and_roles_rendered(self):
        """Test template rendering of all message tag types (success, error, warning, info)."""
        messages_to_test = [
            (Message(message_constants.SUCCESS, "Operation succeeded."), "settings-alert-success", "status"),
            (Message(message_constants.ERROR, "Critical operation failed."), "settings-alert-danger", "alert"),
            (Message(message_constants.WARNING, "Security warning issued."), "settings-alert-warning", "alert"),
            (Message(message_constants.INFO, "Informational note."), "settings-alert-info", "status"),
        ]

        from django.template.loader import render_to_string
        from django.test import RequestFactory

        rf = RequestFactory()
        req = rf.get(self.url)
        req.user = self.user

        for msg_obj, expected_class, expected_role in messages_to_test:
            rendered = render_to_string(
                "accounts/settings.html",
                {
                    "user": self.user,
                    "profile": self.profile,
                    "messages": [msg_obj],
                    "cooldown_status": {"can_change": True},
                },
                request=req,
            )
            self.assertEqual(
                rendered.count(msg_obj.message),
                1,
                f"Message '{msg_obj.message}' must render exactly once.",
            )
            self.assertIn(expected_class, rendered)
            self.assertIn(f'role="{expected_role}"', rendered)
            self.assertIn('data-action="dismiss-alert"', rendered)

    def test_global_messages_block_still_renders_on_other_pages(self):
        """Global messages container in base.html continues to render for other views (e.g. login)."""
        from django.template.loader import render_to_string
        from django.test import RequestFactory

        rf = RequestFactory()
        req = rf.get("/login/")
        req.user = self.user

        msg = Message(message_constants.INFO, "Global login banner notice.")
        rendered = render_to_string(
            "accounts/login.html",
            {
                "messages": [msg],
            },
            request=req,
        )
        self.assertIn('data-testid="messages-container"', rendered)
        self.assertIn("Global login banner notice.", rendered)

    def test_zero_inline_styles_and_handlers_across_all_major_states(self):
        """Assert zero style= attributes and zero inline on* handlers across all major settings states."""
        # State 1: Default Clean State
        resp1 = self.client.get(self.url)
        self._assert_zero_inline_styles_and_handlers(resp1.content.decode("utf-8"), "Default State")

        # State 2: Username Cooldown Active
        self.profile.username_changed_at = timezone.now() - timedelta(days=2)
        self.profile.save()
        resp2 = self.client.get(self.url)
        self._assert_zero_inline_styles_and_handlers(resp2.content.decode("utf-8"), "Cooldown State")

        # State 3: Pending Email Change Flow
        PendingEmailChange.objects.create(user=self.user, new_email="pending_test@passli.dev")
        resp3 = self.client.get(self.url)
        self._assert_zero_inline_styles_and_handlers(resp3.content.decode("utf-8"), "Pending Email State")

        # State 4: Password Reset OTP Pending Flow
        session = self.client.session
        session["pwd_reset_otp_requested"] = True
        session.save()
        resp4 = self.client.get(self.url)
        self._assert_zero_inline_styles_and_handlers(resp4.content.decode("utf-8"), "Reset OTP Pending State")

        # State 5: Password Reset Authorized Window
        session["pwd_reset_otp_requested"] = False
        session[PASSWORD_RESET_SESSION_KEY] = timezone.now().isoformat()
        session.save()
        resp5 = self.client.get(self.url)
        self._assert_zero_inline_styles_and_handlers(resp5.content.decode("utf-8"), "Reset Authorized State")

        # State 6: Password Lockout Throttled
        session[PASSWORD_RESET_SESSION_KEY] = None
        session.save()
        ActionThrottle.objects.create(
            user=self.user,
            action="password_change",
            failed_attempts=5,
            locked_until=timezone.now() + timedelta(minutes=15),
        )
        resp6 = self.client.get(self.url)
        self._assert_zero_inline_styles_and_handlers(resp6.content.decode("utf-8"), "Password Throttled State")

        # State 7: Empty Activity State
        AccountEvent.objects.filter(user=self.user).delete()
        resp7 = self.client.get(self.url)
        self._assert_zero_inline_styles_and_handlers(resp7.content.decode("utf-8"), "Empty Activity State")

    def _assert_zero_inline_styles_and_handlers(self, html_content: str, state_name: str):
        # Extract the settings container from the rendered page (content defined in settings.html)
        container_start = html_content.find('<div class="settings-container">')
        self.assertNotEqual(container_start, -1, f"Settings container not found in {state_name}")
        container_end = html_content.find("<!-- Backdrop for mobile bottom sheets", container_start)
        if container_end != -1:
            settings_html = html_content[container_start:container_end]
        else:
            settings_html = html_content[container_start:]

        style_matches = re.findall(r"<[^>]*\bstyle\s*=[^>]*>", settings_html, re.IGNORECASE)
        self.assertEqual(
            len(style_matches),
            0,
            f"Found inline style attribute(s) in {state_name}: {style_matches}",
        )

        handler_matches = re.findall(r"<[^>]*\bon[a-z]+\s*=[^>]*>", settings_html, re.IGNORECASE)
        self.assertEqual(
            len(handler_matches),
            0,
            f"Found inline event handler(s) in {state_name}: {handler_matches}",
        )
