"""
User Accounts & Dashboard Test Suite
Validates User Registration, Authentication, Session Lifecycle,
Protected Dashboard Routing, and Vault Statistics Metrics.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from tests.unit import get_test_password

User = get_user_model()


class AccountsAndDashboardTests(TestCase):
    """Test suite covering Authentication flows and Dashboard views."""

    def setUp(self):
        self.client = Client()
        self.username = "vaultmaster"
        self.email = "vaultmaster@passli.dev"
        self.password = get_test_password()
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
        reg_pw = get_test_password()
        new_data = {
            'username': 'newuser2026',
            'email': 'newuser2026@passli.dev',
            'password1': reg_pw,
            'password2': reg_pw,
        }
        response = self.client.post(reverse('register'), data=new_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/dashboard.html')
        self.assertTrue(User.objects.filter(username='newuser2026').exists())
        self.assertContains(response, 'Personal Vault Dashboard')
        self.assertContains(response, 'Welcome to Passli, newuser2026!')

    def test_register_user_duplicate_username(self):
        """Verify registration rejects existing username."""
        dup_pw = get_test_password()
        dup_data = {
            'username': self.username,
            'email': 'different@passli.dev',
            'password1': dup_pw,
            'password2': dup_pw,
        }
        response = self.client.post(reverse('register'), data=dup_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A user with that username already exists.')

    def test_register_user_duplicate_email(self):
        """Verify registration rejects existing email."""
        dup_pw = get_test_password()
        dup_data = {
            'username': 'uniqueuser',
            'email': self.email,
            'password1': dup_pw,
            'password2': dup_pw,
        }
        response = self.client.post(reverse('register'), data=dup_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account with this email address already exists.')

    def test_register_user_password_mismatch(self):
        """Verify registration rejects mismatching passwords."""
        mismatch_data = {
            'username': 'mismatchuser',
            'email': 'mismatch@passli.dev',
            'password1': get_test_password(),
            'password2': get_test_password(),
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
            'password': get_test_password(),
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
        self.assertIn('Vault Storage: AES-256-GCM', content)
        self.assertIn('VAULT RECORDS', content)
        self.assertIn('ACTIVE PASSES', content)
        self.assertIn('STORAGE QUOTA', content)
        self.assertIn('No Active Share Passes', content)
        self.assertIn('Your Vault is Empty', content)

    def test_ensure_superadmin_fails_safe_when_no_env_vars(self):
        """Verify ensure_superadmin does not create users or hardcode default credentials when env vars are missing."""
        import os
        from io import StringIO
        from django.core.management import call_command

        # Ensure env vars are unset
        old_u = os.environ.pop('DJANGO_SUPERUSER_USERNAME', None)
        old_p = os.environ.pop('DJANGO_SUPERUSER_PASSWORD', None)
        old_e = os.environ.pop('DJANGO_SUPERUSER_EMAIL', None)
        try:
            out = StringIO()
            initial_count = User.objects.filter(is_superuser=True).count()
            call_command('ensure_superadmin', stdout=out)
            self.assertEqual(User.objects.filter(is_superuser=True).count(), initial_count)
            self.assertIn('Skipping primary superadmin creation', out.getvalue())
        finally:
            if old_u:
                os.environ['DJANGO_SUPERUSER_USERNAME'] = old_u
            if old_p:
                os.environ['DJANGO_SUPERUSER_PASSWORD'] = old_p
            if old_e:
                os.environ['DJANGO_SUPERUSER_EMAIL'] = old_e

    def test_ensure_superadmin_creates_admin_and_preserves_password(self):
        """Verify ensure_superadmin creates admin from env and never resets changed password on subsequent runs."""
        import os
        from io import StringIO
        from django.core.management import call_command
        from django.contrib.auth import authenticate

        test_user = "test_ops_admin"
        initial_pw = get_test_password()
        changed_pw = get_test_password()

        os.environ['DJANGO_SUPERUSER_USERNAME'] = test_user
        os.environ['DJANGO_SUPERUSER_PASSWORD'] = initial_pw
        os.environ['DJANGO_SUPERUSER_EMAIL'] = "ops@passli.dev"

        try:
            out = StringIO()
            # 1. First run creates superadmin
            call_command('ensure_superadmin', stdout=out)
            admin_user = User.objects.get(username=test_user)
            self.assertTrue(admin_user.is_superuser)
            self.assertTrue(admin_user.is_staff)
            self.assertIsNotNone(authenticate(username=test_user, password=initial_pw))

            # 2. Admin changes their password in production/UI
            admin_user.set_password(changed_pw)
            admin_user.save()
            self.assertIsNotNone(authenticate(username=test_user, password=changed_pw))

            # 3. Subsequent redeploy / startup run must NOT reset password
            out2 = StringIO()
            call_command('ensure_superadmin', stdout=out2)
            self.assertIn("preserved existing password", out2.getvalue())

            # Password should still be the modified password, NOT reset to initial_pw
            self.assertIsNotNone(authenticate(username=test_user, password=changed_pw))
            self.assertIsNone(authenticate(username=test_user, password=initial_pw))
        finally:
            os.environ.pop('DJANGO_SUPERUSER_USERNAME', None)
            os.environ.pop('DJANGO_SUPERUSER_PASSWORD', None)
            os.environ.pop('DJANGO_SUPERUSER_EMAIL', None)
            User.objects.filter(username=test_user).delete()


class LoginLockoutTests(TestCase):
    """
    Test suite for database-backed per-username and per-IP exponential brute-force lockout.
    """

    def setUp(self):
        self.username = "bruteforcetarget"
        self.email = "target@passli.dev"
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )
        self.login_url = reverse('login')
        self.client_ip = "198.51.100.77"

    def test_five_failed_logins_trigger_lockout_429(self):
        """Five consecutive failed logins trigger lockout and return HTTP 429 with Retry-After."""
        from accounts.models import LoginLockout

        client = Client()
        for i in range(4):
            res = client.post(
                self.login_url,
                {'username': self.username, 'password': 'WrongPassword123!'},
                REMOTE_ADDR=self.client_ip
            )
            self.assertEqual(res.status_code, 200)

        # 5th attempt reaches threshold and triggers lockout
        res5 = client.post(
            self.login_url,
            {'username': self.username, 'password': 'WrongPassword123!'},
            REMOTE_ADDR=self.client_ip
        )
        self.assertEqual(res5.status_code, 429)
        self.assertIn("Retry-After", res5.headers)
        self.assertEqual(res5.headers["Retry-After"], "60")

        lockout = LoginLockout.objects.get(username=self.username, ip_address=self.client_ip)
        self.assertEqual(lockout.failed_attempts, 5)
        self.assertTrue(lockout.is_locked)

        # 6th attempt while locked out is rejected immediately with 429
        res6 = client.post(
            self.login_url,
            {'username': self.username, 'password': self.password},
            REMOTE_ADDR=self.client_ip
        )
        self.assertEqual(res6.status_code, 429)

    def test_successful_login_resets_lockout_counters(self):
        """A valid login resets failed_attempts to 0 and clears locked_until."""
        from accounts.models import LoginLockout

        client = Client()
        # 2 failed attempts
        for _ in range(2):
            client.post(
                self.login_url,
                {'username': self.username, 'password': 'WrongPassword!'},
                REMOTE_ADDR=self.client_ip
            )

        lockout = LoginLockout.objects.get(username=self.username, ip_address=self.client_ip)
        self.assertEqual(lockout.failed_attempts, 2)

        # Successful login
        res_ok = client.post(
            self.login_url,
            {'username': self.username, 'password': self.password},
            REMOTE_ADDR=self.client_ip
        )
        self.assertEqual(res_ok.status_code, 302)

        lockout.refresh_from_db()
        self.assertEqual(lockout.failed_attempts, 0)
        self.assertFalse(lockout.is_locked)

    def test_lockout_isolated_by_username_and_ip(self):
        """Lockout on one username/IP does not block a different user or IP."""
        client = Client()
        # Trigger lockout for user1 on client_ip
        for _ in range(5):
            client.post(
                self.login_url,
                {'username': self.username, 'password': 'WrongPassword!'},
                REMOTE_ADDR=self.client_ip
            )

        # Different IP for same user is not locked out
        res_diff_ip = client.post(
            self.login_url,
            {'username': self.username, 'password': 'WrongPassword!'},
            REMOTE_ADDR="203.0.113.88"
        )
        self.assertEqual(res_diff_ip.status_code, 200)

        # Different user on same IP is not locked out
        User.objects.create_user(
            username="otheruser_sec",
            email="other@passli.dev",
            password=self.password
        )
        res_diff_user = client.post(
            self.login_url,
            {'username': "otheruser_sec", 'password': self.password},
            REMOTE_ADDR=self.client_ip
        )
        self.assertEqual(res_diff_user.status_code, 302)


