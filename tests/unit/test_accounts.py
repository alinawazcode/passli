"""
User Accounts & Dashboard Test Suite
Validates User Registration, Authentication, Session Lifecycle,
Protected Dashboard Routing, and Vault Statistics Metrics.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class AccountsAndDashboardTests(TestCase):
    """Test suite covering Authentication flows and Dashboard views."""

    def setUp(self):
        self.client = Client()
        self.username = "vaultmaster"
        self.email = "vaultmaster@passli.dev"
        self.password = "ComplexPassphrase2026!"
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )

    def test_register_page_renders_cleanly(self):
        """Verify registration page loads with HTTP 200 and required fields."""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')
        self.assertContains(response, 'Create Personal Vault')
        self.assertContains(response, 'Master Passphrase')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')

    def test_register_user_success(self):
        """Verify new user registration creates user and redirects to dashboard."""
        new_data = {
            'username': 'newuser2026',
            'email': 'newuser2026@passli.dev',
            'password1': 'AlphaBravoSecure2026!',
            'password2': 'AlphaBravoSecure2026!',
        }
        response = self.client.post(reverse('register'), data=new_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/dashboard.html')
        self.assertTrue(User.objects.filter(username='newuser2026').exists())
        self.assertContains(response, 'Personal Vault Dashboard')
        self.assertContains(response, 'Welcome to Passli, newuser2026!')

    def test_register_user_duplicate_username(self):
        """Verify registration rejects existing username."""
        dup_data = {
            'username': self.username,
            'email': 'different@passli.dev',
            'password1': 'AnotherPassword2026!',
            'password2': 'AnotherPassword2026!',
        }
        response = self.client.post(reverse('register'), data=dup_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A user with that username already exists.')

    def test_register_user_duplicate_email(self):
        """Verify registration rejects existing email."""
        dup_data = {
            'username': 'uniqueuser',
            'email': self.email,
            'password1': 'AnotherPassword2026!',
            'password2': 'AnotherPassword2026!',
        }
        response = self.client.post(reverse('register'), data=dup_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account with this email address already exists.')

    def test_register_user_password_mismatch(self):
        """Verify registration rejects mismatching passwords."""
        mismatch_data = {
            'username': 'mismatchuser',
            'email': 'mismatch@passli.dev',
            'password1': 'PasswordOne2026!',
            'password2': 'PasswordTwo2026!',
        }
        response = self.client.post(reverse('register'), data=mismatch_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match.")

    def test_login_page_renders_cleanly(self):
        """Verify login page loads with HTTP 200 and required fields."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, 'Access Personal Vault')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_login_user_success(self):
        """Verify valid credentials authenticate user and redirect to dashboard."""
        login_data = {
            'username': self.username,
            'password': self.password,
        }
        response = self.client.post(reverse('login'), data=login_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/dashboard.html')
        self.assertContains(response, f'Welcome back, {self.username}!')
        self.assertContains(response, 'Personal Vault Dashboard')

    def test_login_user_invalid_credentials(self):
        """Verify invalid credentials render error alert."""
        login_data = {
            'username': self.username,
            'password': 'WrongPassword!',
        }
        response = self.client.post(reverse('login'), data=login_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, 'Invalid username or password.')

    def test_logout_user(self):
        """Verify POST logout terminates session and redirects to landing page."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/landing.html')
        self.assertContains(response, 'You have been securely signed out.')

    def test_dashboard_access_unauthenticated_redirects_to_login(self):
        """Verify unauthenticated requests to dashboard redirect to login page."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_access_authenticated_success(self):
        """Verify authenticated dashboard displays metrics, status, and empty states."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/dashboard.html')
        self.assertTemplateUsed(response, 'base.html')

        content = response.content.decode('utf-8')
        self.assertIn('Personal Vault Dashboard', content)
        self.assertIn(self.email, content)
        self.assertIn('Zero-Knowledge Envelope: <strong>ACTIVE</strong>', content)
        self.assertIn('VAULT RECORDS', content)
        self.assertIn('ACTIVE PASSES', content)
        self.assertIn('STORAGE QUOTA', content)
        self.assertIn('No Active Share Passes', content)
        self.assertIn('Your Vault is Empty', content)
