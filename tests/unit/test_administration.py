"""
Unit Test Suite for Passli Administration Console:
Validates @superadmin_required access guards, overview analytics, user management,
document inventory inspection & deletion, share pass revocation, and security audit log feeds.
"""

from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from documents.models import Document
from sharing.models import SharePass
from sharing.utils import generate_share_key
from audit.models import ShareAccessLog

from tests.unit import get_test_password

User = get_user_model()


class AdministrationConsoleTests(TestCase):
    """Test suite covering the custom website administration console."""

    def setUp(self):
        self.client = Client()
        self.password = get_test_password()

        # Regular non-staff user
        self.regular_user = User.objects.create_user(
            username="regularuser",
            email="regular@passli.dev",
            password=self.password
        )

        # Staff admin user
        self.staff_user = User.objects.create_user(
            username="staffadmin",
            email="staff@passli.dev",
            password=self.password,
            is_staff=True
        )

        # Superuser
        self.super_user = User.objects.create_superuser(
            username="rootadmin",
            email="root@passli.dev",
            password=self.password
        )

        # Create sample documents
        self.doc1 = Document.objects.create(
            user=self.regular_user,
            title="Passport_Scan.pdf",
            category="personal",
            file=SimpleUploadedFile("Passport_Scan.pdf", b"%PDF-1.4 sample passport", content_type="application/pdf")
        )
        self.doc2 = Document.objects.create(
            user=self.staff_user,
            title="Medical_Chart.pdf",
            category="medical",
            file=SimpleUploadedFile("Medical_Chart.pdf", b"%PDF-1.4 sample medical", content_type="application/pdf")
        )

        # Create active share pass
        raw_key = generate_share_key()
        self.active_pass = SharePass.objects.create(
            owner=self.regular_user,
            title="HR Verification Pass",
            expires_at=timezone.now() + timedelta(days=2),
            can_download=True,
            max_uses=5,
            access_count=1,
            is_revoked=False
        )
        self.active_pass.set_key(raw_key)
        self.active_pass.save()
        self.active_pass.documents.add(self.doc1)

        # Create audit log directly
        self.audit_log = ShareAccessLog.objects.create(
            share_pass=self.active_pass,
            document=self.doc1,
            event_type=ShareAccessLog.EventType.KEY_SUCCESS,
            status=ShareAccessLog.Status.SUCCESS,
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 TestBrowser",
            details="Pass accessed successfully"
        )

    def test_anonymous_user_redirected(self):
        """Anonymous requests to admin dashboard are redirected to login."""
        endpoints = [
            reverse('admin_dashboard_overview'),
            reverse('admin_dashboard_users'),
            reverse('admin_dashboard_documents'),
            reverse('admin_dashboard_passes'),
            reverse('admin_dashboard_audit'),
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)

    def test_non_staff_user_denied(self):
        """Non-staff logged-in users are redirected away from admin dashboard."""
        self.client.force_login(self.regular_user)
        endpoints = [
            reverse('admin_dashboard_overview'),
            reverse('admin_dashboard_users'),
            reverse('admin_dashboard_documents'),
            reverse('admin_dashboard_passes'),
            reverse('admin_dashboard_audit'),
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)

    def test_staff_user_can_access_all_tabs(self):
        """Staff members can view all admin console tabs with HTTP 200."""
        self.client.force_login(self.staff_user)

        # 1. Overview Tab
        resp_overview = self.client.get(reverse('admin_dashboard_overview'))
        self.assertEqual(resp_overview.status_code, 200)
        self.assertContains(resp_overview, "Platform Administration Console")
        self.assertContains(resp_overview, "Total Users")

        # 2. Users Tab
        resp_users = self.client.get(reverse('admin_dashboard_users'))
        self.assertEqual(resp_users.status_code, 200)
        self.assertContains(resp_users, "User Accounts")
        self.assertContains(resp_users, "regularuser")

        # 3. Documents Tab
        resp_docs = self.client.get(reverse('admin_dashboard_documents'))
        self.assertEqual(resp_docs.status_code, 200)
        self.assertContains(resp_docs, "Vault Storage & Files")
        self.assertContains(resp_docs, "Passport_Scan.pdf")

        # 4. Passes Tab
        resp_passes = self.client.get(reverse('admin_dashboard_passes'))
        self.assertEqual(resp_passes.status_code, 200)
        self.assertContains(resp_passes, "Share Pass Operations")
        self.assertContains(resp_passes, "HR Verification Pass")

        # 5. Audit Tab
        resp_audit = self.client.get(reverse('admin_dashboard_audit'))
        self.assertEqual(resp_audit.status_code, 200)
        self.assertContains(resp_audit, "Global Audit & Threats")
        self.assertContains(resp_audit, "192.168.1.50")

    def test_admin_toggle_user_active_status(self):
        """Staff can deactivate and reactivate a user account."""
        self.client.force_login(self.staff_user)
        self.assertTrue(self.regular_user.is_active)

        url = reverse('admin_user_toggle_status', kwargs={'user_id': self.regular_user.id})
        response = self.client.post(url, {'action_type': 'toggle_active'})
        self.assertEqual(response.status_code, 302)

        self.regular_user.refresh_from_db()
        self.assertFalse(self.regular_user.is_active)

        # Reactivate
        response = self.client.post(url, {'action_type': 'toggle_active'})
        self.assertEqual(response.status_code, 302)
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_active)

    def test_admin_toggle_user_staff_role_by_superuser(self):
        """Superusers can toggle staff role for another user."""
        self.client.force_login(self.super_user)
        self.assertFalse(self.regular_user.is_staff)

        url = reverse('admin_user_toggle_status', kwargs={'user_id': self.regular_user.id})
        response = self.client.post(url, {'action_type': 'toggle_staff'})
        self.assertEqual(response.status_code, 302)

        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_staff)

    def test_admin_revoke_share_pass(self):
        """Staff can immediately revoke an active share pass from the admin console."""
        self.client.force_login(self.staff_user)
        self.assertFalse(self.active_pass.is_revoked)

        url = reverse('admin_pass_revoke', kwargs={'pass_id': self.active_pass.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.active_pass.refresh_from_db()
        self.assertTrue(self.active_pass.is_revoked)

    def test_admin_delete_document(self):
        """Staff can delete a vault document and purge its record."""
        self.client.force_login(self.staff_user)
        doc_id = self.doc1.id

        url = reverse('admin_document_delete', kwargs={'doc_id': doc_id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.assertFalse(Document.objects.filter(id=doc_id).exists())

    def test_admin_audit_filtering(self):
        """Staff can filter audit logs by status, event type, and search query."""
        self.client.force_login(self.staff_user)

        url = reverse('admin_dashboard_audit') + "?status=success&event=key_success&q=192.168.1.50"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "192.168.1.50")

    def test_ensure_superadmin_command(self):
        """Verify ensure_superadmin creates configured superadmins from environment variables."""
        import os
        from django.core.management import call_command
        from django.contrib.auth import authenticate
        from io import StringIO

        admin_pw = get_test_password()
        superadmin_pw = get_test_password()
        os.environ['DJANGO_SUPERUSER_USERNAME'] = 'admin'
        os.environ['DJANGO_SUPERUSER_PASSWORD'] = admin_pw
        os.environ['DJANGO_SECONDARY_SUPERUSER_USERNAME'] = 'superadmin'
        os.environ['DJANGO_SECONDARY_SUPERUSER_PASSWORD'] = superadmin_pw

        try:
            out = StringIO()
            call_command('ensure_superadmin', stdout=out)

            # Verify superadmin user exists and is fully privileged
            superadmin = User.objects.get(username='superadmin')
            self.assertTrue(superadmin.is_superuser)
            self.assertTrue(superadmin.is_staff)
            self.assertTrue(superadmin.is_active)
            self.assertIsNotNone(authenticate(username='superadmin', password=superadmin_pw))

            # Verify admin user exists and is fully privileged
            admin = User.objects.get(username='admin')
            self.assertTrue(admin.is_superuser)
            self.assertTrue(admin.is_staff)
            self.assertTrue(admin.is_active)
            self.assertIsNotNone(authenticate(username='admin', password=admin_pw))
        finally:
            os.environ.pop('DJANGO_SUPERUSER_USERNAME', None)
            os.environ.pop('DJANGO_SUPERUSER_PASSWORD', None)
            os.environ.pop('DJANGO_SECONDARY_SUPERUSER_USERNAME', None)
            os.environ.pop('DJANGO_SECONDARY_SUPERUSER_PASSWORD', None)


