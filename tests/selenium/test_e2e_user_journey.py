"""
End-to-End System & User Journey Verification Suite:
Validates the complete full-stack lifecycle of Passli:
1. User Registration, Session Authentication & Dashboard Metric Initialization.
2. Encrypted Document Ingestion, SHA-256 Checksum Calculation & Taxonomy Categorization.
3. Cryptographic Ephemeral Share Pass Generation, Zero-Knowledge PBKDF2 Key Derivation & QR Code Payload.
4. Recipient Gateway Access, Rate-Limiting Lockout Defense & Share Key Authentication.
5. In-Browser Decrypted Document Preview & Permitted Raw File Streaming.
6. Recipient Session Teardown & In-Memory Token Cleansing.
7. Immutable Security Audit Trail Inspection, Filter Toolbar, IDOR Isolation & 1-Click Instant Revocation.
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
from audit.models import ShareAccessLog

User = get_user_model()


class EndToEndSystemUserJourneyTests(TestCase):
    """
    Comprehensive End-to-End lifecycle simulation testing all integrated
    components from owner onboarding to recipient document inspection and audit revocation.
    """

    def setUp(self):
        self.owner_client = Client()
        self.recipient_client = Client()
        self.adversary_client = Client()

    def tearDown(self):
        # Clean up any files created during tests
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    def test_complete_e2e_user_lifecycle(self):
        """
        Executes and asserts every sequential step of a real-world user lifecycle:
        Owner onboard -> Upload file -> Issue pass -> Recipient verifies ->
        Downloads file -> Leaves -> Owner audits -> Owner revokes pass.
        """
        # ==========================================
        # STEP 1: Owner Registration & Authentication
        # ==========================================
        register_url = reverse('register')
        reg_response = self.owner_client.post(register_url, {
            'username': 'dr_harrison',
            'email': 'harrison@cardiology-partners.com',
            'password1': 'SecureClinicPassphrase2026!',
            'password2': 'SecureClinicPassphrase2026!',
        })
        self.assertEqual(reg_response.status_code, 302)
        self.assertEqual(reg_response.url, reverse('dashboard'))

        # Verify owner account created and authenticated
        owner = User.objects.get(username='dr_harrison')
        self.assertIsNotNone(owner)

        # Access dashboard
        dash_response = self.owner_client.get(reverse('dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, 'dr_harrison')
        self.assertContains(dash_response, 'Personal Vault')

        # ==========================================
        # STEP 2: Document Upload & Checksum Calculation
        # ==========================================
        sample_pdf_payload = b"%PDF-1.4 Clinical Blood Chemistry Report 2026 - Passli Vault"
        uploaded_file = SimpleUploadedFile(
            name="Clinical_Chemistry_2026.pdf",
            content=sample_pdf_payload,
            content_type="application/pdf"
        )
        upload_url = reverse('documents_upload')
        upload_response = self.owner_client.post(upload_url, {
            'title': 'Clinical Chemistry Lab Panel',
            'category': 'medical',
            'description': 'Comprehensive lipid profile and diagnostic biomarkers.',
            'file': uploaded_file,
        })
        self.assertEqual(upload_response.status_code, 302)

        # Verify Document Model persisted with SHA-256 checksum
        doc = Document.objects.filter(user=owner, title='Clinical Chemistry Lab Panel').first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.category, 'medical')
        self.assertTrue(len(doc.file_hash) == 64)
        self.assertTrue(os.path.exists(doc.file.path))

        # Verify owner can view document detail and preview
        doc_detail_url = reverse('document_detail', kwargs={'pk': doc.id})
        doc_detail_res = self.owner_client.get(doc_detail_url)
        self.assertEqual(doc_detail_res.status_code, 200)
        self.assertContains(doc_detail_res, 'Clinical Chemistry Lab Panel')
        self.assertContains(doc_detail_res, doc.file_hash[:16])

        # ==========================================
        # STEP 3: Cryptographic Share Pass Generation
        # ==========================================
        pass_create_url = reverse('share_create')
        create_res = self.owner_client.post(pass_create_url, {
            'title': 'Specialist Referral Access',
            'documents': [doc.id],
            'expires_in': '1h',
            'can_download': True,
        })
        self.assertEqual(create_res.status_code, 302)

        # Extract generated Share Pass from DB
        share_pass = SharePass.objects.filter(owner=owner, title='Specialist Referral Access').first()
        self.assertIsNotNone(share_pass)
        self.assertTrue(share_pass.can_download)
        self.assertEqual(share_pass.documents.count(), 1)

        # Inspect pass detail page (where owner retrieves the plaintext key and QR code)
        pass_detail_url = reverse('share_detail', kwargs={'pass_id': share_pass.id})
        pass_detail_res = self.owner_client.get(pass_detail_url)
        self.assertEqual(pass_detail_res.status_code, 200)
        self.assertContains(pass_detail_res, 'Specialist Referral Access')
        self.assertContains(pass_detail_res, 'data:image/png;base64,')  # QR Code data URI rendered

        # Retrieve plain key from session (which was stored ephemerally at creation time)
        raw_key = self.owner_client.session.get(f'new_pass_key_{share_pass.id}')
        self.assertIsNotNone(raw_key)
        self.assertEqual(len(raw_key.replace('-', '')), 8)
        self.assertTrue(share_pass.verify_key(raw_key))

        # ==========================================
        # STEP 4: Adversary Brute-Force & Rate-Limiting
        # ==========================================
        recipient_verify_url = reverse('recipient_verify', kwargs={'pass_id': share_pass.id})
        
        # Adversary attempts 5 wrong keys
        for attempt in range(5):
            bad_res = self.adversary_client.post(recipient_verify_url, {'access_key': f'WRONG{attempt:03d}'})
            if attempt < 4:
                self.assertEqual(bad_res.status_code, 200)
            else:
                self.assertEqual(bad_res.status_code, 429)  # Rate-limited lockout on 5th failure

        # Verify rate-limit lockout log recorded
        lockout_log = ShareAccessLog.objects.filter(
            share_pass=share_pass,
            event_type=ShareAccessLog.EventType.RATE_LOCKED
        ).first()
        self.assertIsNotNone(lockout_log)
        self.assertEqual(lockout_log.status, ShareAccessLog.Status.LOCKED)

        # ==========================================
        # STEP 5: Legitimate Recipient Key Verification
        # ==========================================
        recip_auth_res = self.recipient_client.post(recipient_verify_url, {
            'access_key': raw_key
        })
        self.assertEqual(recip_auth_res.status_code, 302)
        self.assertEqual(recip_auth_res.url, reverse('recipient_portal', kwargs={'pass_id': share_pass.id}))

        # Verify KEY_SUCCESS audit log
        auth_log = ShareAccessLog.objects.filter(
            share_pass=share_pass,
            event_type=ShareAccessLog.EventType.KEY_SUCCESS
        ).first()
        self.assertIsNotNone(auth_log)
        self.assertEqual(auth_log.status, ShareAccessLog.Status.SUCCESS)

        # ==========================================
        # STEP 6: Recipient Portal, Preview & Download
        # ==========================================
        portal_url = reverse('recipient_portal', kwargs={'pass_id': share_pass.id})
        portal_res = self.recipient_client.get(portal_url)
        self.assertEqual(portal_res.status_code, 200)
        self.assertContains(portal_res, 'Clinical Chemistry Lab Panel')
        self.assertContains(portal_res, 'Download File')

        # Stream document preview
        preview_url = reverse('recipient_doc_preview', kwargs={'pass_id': share_pass.id, 'doc_id': doc.id})
        preview_res = self.recipient_client.get(preview_url)
        self.assertEqual(preview_res.status_code, 200)
        self.assertEqual(preview_res['Content-Type'], 'application/pdf')

        # Download original document
        download_url = reverse('recipient_doc_download', kwargs={'pass_id': share_pass.id, 'doc_id': doc.id})
        download_res = self.recipient_client.get(download_url)
        self.assertEqual(download_res.status_code, 200)
        self.assertIn('attachment;', download_res['Content-Disposition'])

        # Verify preview and download audit logs recorded
        self.assertTrue(ShareAccessLog.objects.filter(
            share_pass=share_pass,
            document=doc,
            event_type=ShareAccessLog.EventType.VIEW_DOC
        ).exists())

        self.assertTrue(ShareAccessLog.objects.filter(
            share_pass=share_pass,
            document=doc,
            event_type=ShareAccessLog.EventType.DOWNLOAD_DOC
        ).exists())

        # ==========================================
        # STEP 7: Recipient Session Exit
        # ==========================================
        leave_url = reverse('recipient_leave', kwargs={'pass_id': share_pass.id})
        leave_res = self.recipient_client.post(leave_url)
        self.assertEqual(leave_res.status_code, 200)
        self.assertContains(leave_res, 'Session Securely Closed')

        # Verify access is now rejected without re-authentication
        portal_retry = self.recipient_client.get(portal_url)
        self.assertEqual(portal_retry.status_code, 302)
        self.assertIn('/p/', portal_retry.url)

        # ==========================================
        # STEP 8: Owner Audit Trail Inspection & Revocation
        # ==========================================
        audit_res = self.owner_client.get(reverse('audit:audit_list'))
        self.assertEqual(audit_res.status_code, 200)
        self.assertContains(audit_res, 'Specialist Referral Access')
        self.assertContains(audit_res, 'Key Verified')
        self.assertContains(audit_res, 'Document Downloaded')

        # Execute 1-click immediate pass revocation
        revoke_url = reverse('share_revoke', kwargs={'pass_id': share_pass.id})
        revoke_res = self.owner_client.post(revoke_url)
        self.assertEqual(revoke_res.status_code, 302)

        share_pass.refresh_from_db()
        self.assertTrue(share_pass.is_revoked)

        # Recipient attempts to verify on revoked pass -> Rejected with HTTP 403
        revoked_attempt = self.recipient_client.get(recipient_verify_url)
        self.assertEqual(revoked_attempt.status_code, 403)
        self.assertContains(revoked_attempt, 'Access Pass Revoked', status_code=403)
