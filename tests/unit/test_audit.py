"""
Audit Trail & Security Event Logging Test Suite
Validates Cryptographic Access Audit Trail, Structured Logging Triggers,
Rate-Limiting Lockout Auditing, In-Browser Preview & Download Logging,
Owner Audit Dashboard, and Strict Multi-Tenant IDOR Isolation.
"""

import os
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from documents.models import Document
from sharing.models import SharePass
from sharing.utils import generate_share_key
from audit.models import ShareAccessLog, log_share_event

User = get_user_model()


class AuditTrailTests(TestCase):
    """Test suite covering Audit Trail & Security Event Logging."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="auditowner",
            email="auditowner@passli.dev",
            password="SecurePassphrase2026!"
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="otheruser@passli.dev",
            password="SecurePassphrase2026!"
        )

        # Upload sample test documents
        self.doc1 = Document.objects.create(
            user=self.owner,
            title="Blood_Analysis_2026.pdf",
            category="medical",
            file=SimpleUploadedFile("Blood_Analysis_2026.pdf", b"%PDF-1.4 sample pdf", content_type="application/pdf")
        )
        self.other_doc = Document.objects.create(
            user=self.other_user,
            title="Confidential_Tax.pdf",
            category="financial",
            file=SimpleUploadedFile("Confidential_Tax.pdf", b"%PDF-1.4 tax pdf", content_type="application/pdf")
        )

        # Create active Share Pass for owner
        self.raw_key = generate_share_key()
        self.active_pass = SharePass.objects.create(
            owner=self.owner,
            title="Clinic KYC Records",
            expires_at=timezone.now() + timedelta(hours=2),
            can_download=True,
        )
        self.active_pass.set_key(self.raw_key)
        self.active_pass.save()
        self.active_pass.documents.add(self.doc1)

        # Create Share Pass for other user
        self.other_key = generate_share_key()
        self.other_pass = SharePass.objects.create(
            owner=self.other_user,
            title="Other User Pass",
            expires_at=timezone.now() + timedelta(hours=1),
            can_download=False,
        )
        self.other_pass.set_key(self.other_key)
        self.other_pass.save()
        self.other_pass.documents.add(self.other_doc)

    def tearDown(self):
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    def test_log_share_event_helper(self):
        """Verify helper function records structured audit logs with IP and user-agent."""
        log = log_share_event(
            share_pass=self.active_pass,
            event_type=ShareAccessLog.EventType.KEY_SUCCESS,
            status=ShareAccessLog.Status.SUCCESS,
            details="Manual test event"
        )
        self.assertIsNotNone(log.id)
        self.assertEqual(log.share_pass, self.active_pass)
        self.assertEqual(log.event_type, ShareAccessLog.EventType.KEY_SUCCESS)
        self.assertEqual(log.status, ShareAccessLog.Status.SUCCESS)
        self.assertIn("Clinic KYC Records", str(log))

    def test_key_verification_success_logged_automatically(self):
        """Verify successful recipient key verification creates KEY_SUCCESS log entry."""
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        response = self.client.post(verify_url, {'access_key': self.raw_key})
        self.assertEqual(response.status_code, 302)

        # Verify audit log recorded
        log = ShareAccessLog.objects.filter(
            share_pass=self.active_pass,
            event_type=ShareAccessLog.EventType.KEY_SUCCESS
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, ShareAccessLog.Status.SUCCESS)
        self.assertIn("verified", log.details.lower())

    def test_key_verification_failure_logged(self):
        """Verify invalid key submission creates KEY_FAILED log entry."""
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        response = self.client.post(verify_url, {'access_key': 'WRONGKEY'})
        self.assertEqual(response.status_code, 200)

        log = ShareAccessLog.objects.filter(
            share_pass=self.active_pass,
            event_type=ShareAccessLog.EventType.KEY_FAILED
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, ShareAccessLog.Status.DENIED)

    def test_brute_force_lockout_logged(self):
        """Verify 5 consecutive failed attempts trigger RATE_LOCKED security log."""
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        for i in range(5):
            self.client.post(verify_url, {'access_key': f'BADKEY{i}'})

        lockout_log = ShareAccessLog.objects.filter(
            share_pass=self.active_pass,
            event_type=ShareAccessLog.EventType.RATE_LOCKED
        ).first()
        self.assertIsNotNone(lockout_log)
        self.assertEqual(lockout_log.status, ShareAccessLog.Status.LOCKED)

    def test_expired_pass_attempt_logged(self):
        """Verify access attempt on expired pass creates PASS_EXPIRED log."""
        expired_pass = SharePass.objects.create(
            owner=self.owner,
            title="Expired KYC",
            expires_at=timezone.now() - timedelta(minutes=5),
            can_download=False
        )
        expired_pass.set_key("EXPIRED1")
        expired_pass.save()

        verify_url = reverse('recipient_verify', kwargs={'pass_id': expired_pass.id})
        self.client.get(verify_url)

        log = ShareAccessLog.objects.filter(
            share_pass=expired_pass,
            event_type=ShareAccessLog.EventType.PASS_EXPIRED
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, ShareAccessLog.Status.EXPIRED)

    def test_revoked_pass_attempt_logged(self):
        """Verify access attempt on revoked pass creates PASS_REVOKED log."""
        revoked_pass = SharePass.objects.create(
            owner=self.owner,
            title="Revoked KYC",
            expires_at=timezone.now() + timedelta(hours=1),
            is_revoked=True
        )
        revoked_pass.set_key("REVOKED1")
        revoked_pass.save()

        verify_url = reverse('recipient_verify', kwargs={'pass_id': revoked_pass.id})
        self.client.get(verify_url)

        log = ShareAccessLog.objects.filter(
            share_pass=revoked_pass,
            event_type=ShareAccessLog.EventType.PASS_REVOKED
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, ShareAccessLog.Status.REVOKED)

    def test_document_preview_and_download_logged(self):
        """Verify viewing preview and downloading file creates VIEW_DOC and DOWNLOAD_DOC logs."""
        # 1. Authenticate session
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        self.client.post(verify_url, {'access_key': self.raw_key})

        # 2. Preview document
        preview_url = reverse('recipient_doc_preview', kwargs={
            'pass_id': self.active_pass.id,
            'doc_id': self.doc1.id
        })
        self.client.get(preview_url)

        view_log = ShareAccessLog.objects.filter(
            share_pass=self.active_pass,
            document=self.doc1,
            event_type=ShareAccessLog.EventType.VIEW_DOC
        ).first()
        self.assertIsNotNone(view_log)
        self.assertEqual(view_log.status, ShareAccessLog.Status.SUCCESS)

        # 3. Download document
        download_url = reverse('recipient_doc_download', kwargs={
            'pass_id': self.active_pass.id,
            'doc_id': self.doc1.id
        })
        self.client.get(download_url)

        dl_log = ShareAccessLog.objects.filter(
            share_pass=self.active_pass,
            document=self.doc1,
            event_type=ShareAccessLog.EventType.DOWNLOAD_DOC
        ).first()
        self.assertIsNotNone(dl_log)
        self.assertEqual(dl_log.status, ShareAccessLog.Status.SUCCESS)

    def test_recipient_leave_session_logged(self):
        """Verify voluntary session exit creates SESSION_LEFT log."""
        # Authenticate
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        self.client.post(verify_url, {'access_key': self.raw_key})

        # Leave session
        leave_url = reverse('recipient_leave', kwargs={'pass_id': self.active_pass.id})
        self.client.post(leave_url)

        leave_log = ShareAccessLog.objects.filter(
            share_pass=self.active_pass,
            event_type=ShareAccessLog.EventType.SESSION_LEFT
        ).first()
        self.assertIsNotNone(leave_log)
        self.assertEqual(leave_log.status, ShareAccessLog.Status.SUCCESS)

    def test_owner_revoke_pass_logged(self):
        """Verify owner revoking a pass logs PASS_REVOKED event."""
        self.client.login(username="auditowner", password="SecurePassphrase2026!")
        revoke_url = reverse('share_revoke', kwargs={'pass_id': self.active_pass.id})
        self.client.post(revoke_url)

        self.active_pass.refresh_from_db()
        self.assertTrue(self.active_pass.is_revoked)

        revoke_log = ShareAccessLog.objects.filter(
            share_pass=self.active_pass,
            event_type=ShareAccessLog.EventType.PASS_REVOKED
        ).first()
        self.assertIsNotNone(revoke_log)
        self.assertEqual(revoke_log.status, ShareAccessLog.Status.REVOKED)
        self.assertIn("auditowner", revoke_log.details)

    def test_audit_list_view_authenticated_renders(self):
        """Verify logged-in owner can load the audit dashboard with metric counters."""
        self.client.login(username="auditowner", password="SecurePassphrase2026!")
        
        # Create a few audit logs
        log_share_event(self.active_pass, ShareAccessLog.EventType.KEY_SUCCESS, status=ShareAccessLog.Status.SUCCESS)
        log_share_event(self.active_pass, ShareAccessLog.EventType.DOWNLOAD_DOC, document=self.doc1, status=ShareAccessLog.Status.SUCCESS)

        response = self.client.get(reverse('audit:audit_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'audit/list.html')
        self.assertContains(response, 'Access & Verification Audit Trail')
        self.assertContains(response, 'Total Events Logged')
        self.assertContains(response, 'Verified Unlocks')

    def test_audit_list_view_unauthenticated_redirects(self):
        """Verify unauthenticated user cannot access audit dashboard."""
        response = self.client.get(reverse('audit:audit_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_audit_list_view_idor_isolation(self):
        """Verify User A CANNOT see User B's audit events (strict IDOR isolation)."""
        # Create audit event for other_user
        log_share_event(
            self.other_pass,
            ShareAccessLog.EventType.KEY_SUCCESS,
            details="Secret Event for Other User"
        )

        # Login as owner
        self.client.login(username="auditowner", password="SecurePassphrase2026!")
        response = self.client.get(reverse('audit:audit_list'))
        self.assertEqual(response.status_code, 200)

        # Verify other user's event does NOT appear in response
        self.assertNotContains(response, "Secret Event for Other User")
        self.assertNotContains(response, str(self.other_pass.id)[:8].upper())

    def test_audit_list_view_filters_and_search(self):
        """Verify filtering by event_type, pass, status, and query works properly."""
        log_share_event(self.active_pass, ShareAccessLog.EventType.KEY_SUCCESS, details="Clinic Success Alpha")
        log_share_event(self.active_pass, ShareAccessLog.EventType.KEY_FAILED, status=ShareAccessLog.Status.DENIED, details="Failed Attempt Beta")

        self.client.login(username="auditowner", password="SecurePassphrase2026!")

        # Filter by event_type=key_failed
        res_filter = self.client.get(reverse('audit:audit_list') + '?event=key_failed')
        self.assertEqual(res_filter.status_code, 200)
        self.assertContains(res_filter, "Failed Attempt Beta")
        self.assertNotContains(res_filter, "Clinic Success Alpha")

        # Search query q=Alpha
        res_search = self.client.get(reverse('audit:audit_list') + '?q=Alpha')
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, "Clinic Success Alpha")
        self.assertNotContains(res_search, "Failed Attempt Beta")
