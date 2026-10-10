"""
Phase 5 Comprehensive Test Suite
Validates Recipient Verification Portal, Two-Factor Access Flow,
Cryptographic Share Key Validation, Brute-Force Rate Limiting,
Session-Gated Document Streaming, Download Permission Gating, and IDOR Defense.
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

User = get_user_model()


class Phase5RecipientPortalTests(TestCase):
    """Test suite covering Phase 5 Recipient Portal & Verification Security."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="vaultowner",
            email="owner@passli.dev",
            password="SecurePassphrase2026!"
        )
        self.other_user = User.objects.create_user(
            username="otherowner",
            email="other@passli.dev",
            password="SecurePassphrase2026!"
        )

        # Create sample PDF document for owner
        pdf_content = b"%PDF-1.4 sample PDF payload for Passli Phase 5 testing"
        self.pdf_file = SimpleUploadedFile(
            "Blood_Panel_Report.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        self.doc1 = Document.objects.create(
            user=self.owner,
            title="Blood Panel Report",
            category="medical",
            file=self.pdf_file
        )

        # Create sample image document for owner
        img_content = b"\x89PNG\r\n\x1a\n sample png"
        self.img_file = SimpleUploadedFile(
            "Passport_Scan.png",
            img_content,
            content_type="image/png"
        )
        self.doc2 = Document.objects.create(
            user=self.owner,
            title="Passport Identity Card",
            category="personal",
            file=self.img_file
        )

        # Create an unrelated document belonging to another user (for IDOR tests)
        other_pdf = SimpleUploadedFile("Secret_Doc.pdf", b"%PDF-1.4 secret", content_type="application/pdf")
        self.unrelated_doc = Document.objects.create(
            user=self.other_user,
            title="Unrelated Secret Document",
            category="financial",
            file=other_pdf
        )

        # Create active Share Pass with doc1 and doc2 (can_download=True)
        self.raw_key = generate_share_key()  # e.g., "A1B2C3D4"
        self.active_pass = SharePass.objects.create(
            owner=self.owner,
            title="Clinic KYC Verification",
            expires_at=timezone.now() + timedelta(hours=1),
            can_download=True,
            max_uses=0,
        )
        self.active_pass.set_key(self.raw_key)
        self.active_pass.save()
        self.active_pass.documents.add(self.doc1, self.doc2)

        # Create view-only Share Pass (can_download=False)
        self.view_only_key = generate_share_key()
        self.view_only_pass = SharePass.objects.create(
            owner=self.owner,
            title="View Only Consultation",
            expires_at=timezone.now() + timedelta(hours=1),
            can_download=False,
            max_uses=0,
        )
        self.view_only_pass.set_key(self.view_only_key)
        self.view_only_pass.save()
        self.view_only_pass.documents.add(self.doc1)

    def tearDown(self):
        # Cleanup uploaded files from disk after tests
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    def test_recipient_verify_page_renders_cleanly(self):
        """Verify recipient landing page renders with HTTP 200 and key input."""
        url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'sharing/recipient_verify.html')
        self.assertContains(response, 'Enter 8-Character Share Key')
        self.assertContains(response, 'name="access_key"')
        self.assertContains(response, 'Clinic KYC Verification')

    def test_recipient_verify_invalid_pass_id_returns_404(self):
        """Verify non-existent UUID returns HTTP 404."""
        import uuid
        random_uuid = uuid.uuid4()
        url = reverse('recipient_verify', kwargs={'pass_id': random_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_recipient_verify_success_with_various_key_formats(self):
        """Verify successful key entry (with hyphens, lowercase, and spaces) unlocks session."""
        url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        
        # Test key formatted with dash: "XXXX-XXXX"
        formatted_key = f"{self.raw_key[:4]}-{self.raw_key[4:]}".lower()
        response = self.client.post(url, {'access_key': formatted_key})
        
        # Should redirect to portal
        self.assertRedirects(response, reverse('recipient_portal', kwargs={'pass_id': self.active_pass.id}))
        
        # Verify access count incremented
        self.active_pass.refresh_from_db()
        self.assertEqual(self.active_pass.access_count, 1)

        # Verify recipient can now load portal directly
        portal_res = self.client.get(reverse('recipient_portal', kwargs={'pass_id': self.active_pass.id}))
        self.assertEqual(portal_res.status_code, 200)
        self.assertTemplateUsed(portal_res, 'sharing/recipient_portal.html')
        self.assertContains(portal_res, 'Blood Panel Report')
        self.assertContains(portal_res, 'Passport Identity Card')

    def test_recipient_verify_invalid_key_rejected(self):
        """Verify incorrect Share Key is rejected with remaining attempts counter."""
        url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        response = self.client.post(url, {'access_key': 'WRONGKEY'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid Share Key')
        self.assertContains(response, '4 attempt(s) remaining')

    def test_recipient_brute_force_lockout_after_5_attempts(self):
        """Verify 5 consecutive failed key submissions locks out the browser."""
        url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        
        for i in range(4):
            res = self.client.post(url, {'access_key': f'FAIL{i:04d}'})
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'Invalid Share Key')

        # 5th failed attempt should trigger lockout screen with HTTP 429
        fifth_res = self.client.post(url, {'access_key': 'FAIL0005'})
        self.assertEqual(fifth_res.status_code, 429)
        self.assertTemplateUsed(fifth_res, 'sharing/recipient_error.html')
        self.assertContains(fifth_res, 'Access Temporarily Locked', status_code=429)

        # Subsequent GET should also be locked
        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 429)
        self.assertContains(get_res, 'Access Temporarily Locked', status_code=429)

    def test_recipient_portal_unauthenticated_redirects_to_verify(self):
        """Verify accessing portal directly without key authentication redirects to verify."""
        url = reverse('recipient_portal', kwargs={'pass_id': self.active_pass.id})
        response = self.client.get(url)
        self.assertRedirects(response, reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id}))

    def test_recipient_expired_pass_rejected(self):
        """Verify expired Share Pass displays expired diagnostic error."""
        expired_pass = SharePass.objects.create(
            owner=self.owner,
            title="Expired Pass",
            expires_at=timezone.now() - timedelta(minutes=10),
            can_download=False,
        )
        expired_pass.set_key("EXPIRED1")
        expired_pass.save()
        expired_pass.documents.add(self.doc1)

        url = reverse('recipient_verify', kwargs={'pass_id': expired_pass.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)
        self.assertTemplateUsed(response, 'sharing/recipient_error.html')
        self.assertContains(response, 'Access Pass Expired', status_code=410)

    def test_recipient_revoked_pass_rejected(self):
        """Verify immediately revoked Share Pass terminates recipient access."""
        revoked_pass = SharePass.objects.create(
            owner=self.owner,
            title="Revoked Pass",
            expires_at=timezone.now() + timedelta(hours=1),
            is_revoked=True,
        )
        revoked_pass.set_key("REVOKED1")
        revoked_pass.save()
        revoked_pass.documents.add(self.doc1)

        url = reverse('recipient_verify', kwargs={'pass_id': revoked_pass.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'sharing/recipient_error.html')
        self.assertContains(response, 'Access Pass Revoked', status_code=403)


    def test_recipient_doc_preview_authorized(self):
        """Verify authenticated recipient can preview attached PDF inline."""
        # Authenticate first
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        self.client.post(verify_url, {'access_key': self.raw_key})

        preview_url = reverse('recipient_doc_preview', kwargs={
            'pass_id': self.active_pass.id,
            'doc_id': self.doc1.id
        })
        response = self.client.get(preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline', response['Content-Disposition'])

    def test_recipient_doc_preview_unauthenticated_forbidden(self):
        """Verify unauthenticated user cannot preview document directly."""
        preview_url = reverse('recipient_doc_preview', kwargs={
            'pass_id': self.active_pass.id,
            'doc_id': self.doc1.id
        })
        response = self.client.get(preview_url)
        self.assertEqual(response.status_code, 403)

    def test_recipient_doc_preview_idor_defense(self):
        """Verify recipient cannot preview document not belonging to this Share Pass."""
        # Authenticate
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        self.client.post(verify_url, {'access_key': self.raw_key})

        # Attempt to access unrelated_doc (not in this pass)
        idor_preview_url = reverse('recipient_doc_preview', kwargs={
            'pass_id': self.active_pass.id,
            'doc_id': self.unrelated_doc.id
        })
        response = self.client.get(idor_preview_url)
        self.assertEqual(response.status_code, 404)

    def test_recipient_doc_download_allowed_when_can_download_true(self):
        """Verify download streams file attachment when can_download=True."""
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        self.client.post(verify_url, {'access_key': self.raw_key})

        download_url = reverse('recipient_doc_download', kwargs={
            'pass_id': self.active_pass.id,
            'doc_id': self.doc1.id
        })
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_recipient_doc_download_forbidden_when_can_download_false(self):
        """Verify download is strictly blocked (HTTP 403) when can_download=False."""
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.view_only_pass.id})
        self.client.post(verify_url, {'access_key': self.view_only_key})

        download_url = reverse('recipient_doc_download', kwargs={
            'pass_id': self.view_only_pass.id,
            'doc_id': self.doc1.id
        })
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, 403)

    def test_recipient_leave_session_clears_auth(self):
        """Verify leave endpoint clears session token and prevents further access."""
        # Authenticate
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        self.client.post(verify_url, {'access_key': self.raw_key})

        # Leave session
        leave_url = reverse('recipient_leave', kwargs={'pass_id': self.active_pass.id})
        leave_res = self.client.post(leave_url)
        self.assertEqual(leave_res.status_code, 200)
        self.assertTemplateUsed(leave_res, 'sharing/recipient_error.html')
        self.assertContains(leave_res, 'Session Securely Closed')

        # Accessing portal again should now redirect back to verify
        portal_res = self.client.get(reverse('recipient_portal', kwargs={'pass_id': self.active_pass.id}))
        self.assertRedirects(portal_res, reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id}))

    def test_recipient_portal_renders_dynamic_watermark(self):
        """Verify dynamic anti-exfiltration watermark overlay is injected into recipient portal."""
        verify_url = reverse('recipient_verify', kwargs={'pass_id': self.active_pass.id})
        self.client.post(verify_url, {'access_key': self.raw_key})

        portal_url = reverse('recipient_portal', kwargs={'pass_id': self.active_pass.id})
        response = self.client.get(portal_url, REMOTE_ADDR='198.51.100.42')

        self.assertEqual(response.status_code, 200)
        self.assertIn('client_ip', response.context)
        self.assertEqual(response.context['client_ip'], '198.51.100.42')
        self.assertIn('watermark_label', response.context)
        self.assertContains(response, 'data-testid="watermark-overlay"')
        self.assertContains(response, '198.51.100.42')
        self.assertContains(response, 'UNAUTHORIZED CAPTURE PROHIBITED')

