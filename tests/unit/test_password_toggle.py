"""
Unit & Template Integration Tests for Show/Hide Password Toggle Buttons.
Validates that every password input across the application includes an
accessible password toggle button with proper ARIA attributes, SVG iconography,
and input-wrapper hierarchy.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import PasswordResetToken
from accounts.services.password_service import PASSWORD_RESET_SESSION_KEY
from tests.unit import get_test_password

User = get_user_model()


class PasswordToggleMarkupTests(TestCase):
    """Test suite ensuring all 12 password fields across 4 views contain toggle markup."""

    def setUp(self):
        self.client = Client()
        self.username = "vaultmaster"
        self.email = "vaultmaster@passli.dev"
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password,
        )

    def test_login_page_password_toggle_markup(self):
        """Verify login view renders toggle button and dual eye SVGs for login-password."""
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn('class="password-input-wrapper"', content)
        self.assertIn('id="login-password"', content)
        self.assertIn('class="password-toggle-btn"', content)
        self.assertIn('aria-controls="login-password"', content)
        self.assertIn('aria-label="Show password"', content)
        self.assertIn('aria-pressed="false"', content)
        self.assertIn("icon-eye", content)
        self.assertIn("icon-eye-off", content)

    def test_register_page_password_toggles_markup(self):
        """Verify registration view renders toggle buttons for both password fields."""
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Must have at least two wrappers
        self.assertGreaterEqual(content.count('class="password-input-wrapper"'), 2)

        # First password field
        self.assertIn('id="reg-password1"', content)
        self.assertIn('aria-controls="reg-password1"', content)

        # Second password confirmation field
        self.assertIn('id="reg-password2"', content)
        self.assertIn('aria-controls="reg-password2"', content)

        # Toggle buttons count
        self.assertGreaterEqual(content.count('class="password-toggle-btn"'), 2)
        self.assertIn('aria-label="Show password"', content)
        self.assertIn('aria-pressed="false"', content)
        self.assertIn("icon-eye", content)
        self.assertIn("icon-eye-off", content)

    def test_password_reset_confirm_toggles_markup(self):
        """Verify password reset confirmation view renders toggle buttons for both fields."""
        _, raw_token = PasswordResetToken.create_token_for_user(self.user)
        url = reverse("password_reset_confirm", kwargs={"token": raw_token})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertGreaterEqual(content.count('class="password-input-wrapper"'), 2)
        self.assertIn('id="reset-password1"', content)
        self.assertIn('aria-controls="reset-password1"', content)
        self.assertIn('id="reset-password2"', content)
        self.assertIn('aria-controls="reset-password2"', content)
        self.assertGreaterEqual(content.count('class="password-toggle-btn"'), 2)
        self.assertIn("icon-eye", content)
        self.assertIn("icon-eye-off", content)

    def test_settings_page_default_password_toggles_markup(self):
        """Verify settings view renders toggle buttons for username, email, and normal password change."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # 1. Username current password
        self.assertIn('id="settings-username-password"', content)
        self.assertIn('aria-controls="settings-username-password"', content)

        # 2. Email current password
        self.assertIn('id="settings-email-password"', content)
        self.assertIn('aria-controls="settings-email-password"', content)

        # 3. Normal change: current password
        self.assertIn('id="settings-current-password"', content)
        self.assertIn('aria-controls="settings-current-password"', content)

        # 4. Normal change: new password
        self.assertIn('id="settings-new-password"', content)
        self.assertIn('aria-controls="settings-new-password"', content)

        # 5. Normal change: confirm password
        self.assertIn('id="settings-confirm-password"', content)
        self.assertIn('aria-controls="settings-confirm-password"', content)

        # Check toggle button class, SVGs, and attributes
        self.assertIn('class="settings-password-toggle-btn"', content)
        self.assertIn("#icon-eye", content)
        self.assertIn("#icon-eye-off", content)
        self.assertIn('aria-label="Show password"', content)
        self.assertIn('aria-pressed="false"', content)

    def test_settings_page_otp_reset_password_toggles_markup(self):
        """Verify settings view in authorized OTP reset state renders toggle buttons for new/confirm."""
        self.client.force_login(self.user)
        session = self.client.session
        session["pwd_reset_otp_requested"] = False
        session[PASSWORD_RESET_SESSION_KEY] = timezone.now().isoformat()
        session.save()

        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # OTP new password
        self.assertIn('id="settings-otp-new-password"', content)
        self.assertIn('aria-controls="settings-otp-new-password"', content)

        # OTP confirm password
        self.assertIn('id="settings-otp-confirm-password"', content)
        self.assertIn('aria-controls="settings-otp-confirm-password"', content)

        self.assertIn('class="settings-password-wrapper"', content)
        self.assertIn('class="settings-password-toggle-btn"', content)
        self.assertIn("#icon-eye", content)
        self.assertIn("#icon-eye-off", content)
