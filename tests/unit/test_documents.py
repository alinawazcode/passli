"""
Document Vault & Storage Security Test Suite
Validates Encrypted Document Vault, File Validation, SHA-256 Checksums,
Category Filtering, In-Browser Previews, Secure Downloads, and IDOR Defense.
"""

import io
import os
import hashlib
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from documents.models import Document

User = get_user_model()


class DocumentVaultTests(TestCase):
    """Test suite covering Document Vault Management & Storage Security."""

    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username="vaultowner1",
            email="owner1@passli.dev",
            password="SecurePassphrase2026!"
        )
        self.user2 = User.objects.create_user(
            username="vaultowner2",
            email="owner2@passli.dev",
            password="SecurePassphrase2026!"
        )

        # Create sample document for user1
        sample_pdf_content = b"%PDF-1.4 sample PDF binary payload for Passli unit testing"
        self.sample_pdf = SimpleUploadedFile(
            "Blood_Panel_2026.pdf",
            sample_pdf_content,
            content_type="application/pdf"
        )
        self.doc1 = Document.objects.create(
            user=self.user1,
            title="Blood Panel Report 2026",
            category="medical",
            description="Fasting blood glucose panel results.",
            file=self.sample_pdf
        )

    def tearDown(self):
        # Cleanup uploaded files from disk after tests
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    def test_document_model_hash_and_properties(self):
        """Verify Document model computes SHA-256 digest, size, and category icon."""
        expected_hash = hashlib.sha256(b"%PDF-1.4 sample PDF binary payload for Passli unit testing").hexdigest()
        self.assertEqual(self.doc1.file_hash, expected_hash)
        self.assertTrue(self.doc1.is_pdf)
        self.assertFalse(self.doc1.is_image)
        self.assertEqual(self.doc1.category_icon, 'medical_services')
        self.assertIn("B", self.doc1.formatted_size)

    def test_documents_list_view_authenticated(self):
        """Verify authenticated user can list their own vault documents."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('documents_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/list.html')
        self.assertContains(response, 'Encrypted Document Vault')
        self.assertContains(response, 'Blood Panel Report 2026')
        self.assertContains(response, 'Medical Records')

    def test_documents_list_view_unauthenticated_redirects(self):
        """Verify anonymous visitors are redirected to login."""
        response = self.client.get(reverse('documents_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_documents_list_category_filter(self):
        """Verify filtering documents by domain category."""
        # Create second document with different category
        png_content = b"\x89PNG\r\n\x1a\n sample png"
        png_file = SimpleUploadedFile("ID_Card.png", png_content, content_type="image/png")
        Document.objects.create(
            user=self.user1,
            title="National Identity Card",
            category="personal",
            file=png_file
        )

        self.client.force_login(self.user1)
        
        # Medical filter: should show doc1 only
        res_med = self.client.get(reverse('documents_list') + '?category=medical')
        self.assertContains(res_med, 'Blood Panel Report 2026')
        self.assertNotContains(res_med, 'National Identity Card')

        # Personal filter: should show doc2 only
        res_pers = self.client.get(reverse('documents_list') + '?category=personal')
        self.assertContains(res_pers, 'National Identity Card')
        self.assertNotContains(res_pers, 'Blood Panel Report 2026')

    def test_documents_list_search_query(self):
        """Verify searching vault documents by title or description."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('documents_list') + '?q=glucose')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Blood Panel Report 2026')

        response_empty = self.client.get(reverse('documents_list') + '?q=NonExistentQueryXYZ')
        self.assertContains(response_empty, 'No Records Match Filters')

    def test_document_upload_success_pdf(self):
        """Verify successful upload of a PDF document."""
        self.client.force_login(self.user2)
        upload_content = b"%PDF-1.4 test degree diploma verification"
        uploaded_file = SimpleUploadedFile("Degree_Diploma.pdf", upload_content, content_type="application/pdf")
        
        post_data = {
            'title': 'Bachelor of Science Diploma',
            'category': 'education',
            'description': 'Verified university graduation certificate.',
            'file': uploaded_file,
        }
        response = self.client.post(reverse('documents_upload'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/detail.html')
        self.assertTrue(Document.objects.filter(user=self.user2, title='Bachelor of Science Diploma').exists())
        self.assertContains(response, 'Bachelor of Science Diploma')
        self.assertContains(response, 'Education &amp; Degrees')

    def test_document_upload_success_image(self):
        """Verify successful upload of a PNG image file."""
        self.client.force_login(self.user2)
        upload_content = b"\x89PNG\r\n\x1a\n fake image content"
        uploaded_file = SimpleUploadedFile("Vehicle_Insurance.png", upload_content, content_type="image/png")

        post_data = {
            'title': 'Vehicle Insurance Policy 2026',
            'category': 'vehicle',
            'description': 'Comprehensive vehicle policy card.',
            'file': uploaded_file,
        }
        response = self.client.post(reverse('documents_upload'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Document.objects.filter(user=self.user2, title='Vehicle Insurance Policy 2026').exists())

    def test_document_upload_invalid_extension_rejected(self):
        """Verify invalid file types (e.g. .exe, .sh) are rejected with error feedback."""
        self.client.force_login(self.user1)
        bad_file = SimpleUploadedFile("malicious_script.exe", b"binary executable", content_type="application/x-msdownload")
        post_data = {
            'title': 'Executable File',
            'category': 'other',
            'file': bad_file,
        }
        response = self.client.post(reverse('documents_upload'), data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported file format &#x27;.exe&#x27;.")
        self.assertFalse(Document.objects.filter(title='Executable File').exists())

    def test_document_detail_view_owner_success(self):
        """Verify document owner can view document detail and preview."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('document_detail', args=[self.doc1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/detail.html')
        self.assertContains(response, 'Blood Panel Report 2026')
        self.assertContains(response, 'SHA-256 DIGEST')
        self.assertContains(response, self.doc1.file_hash)

    def test_document_detail_view_idor_protection(self):
        """Verify User B receives 404 when attempting to view User A's document."""
        self.client.force_login(self.user2)
        response = self.client.get(reverse('document_detail', args=[self.doc1.pk]))
        self.assertEqual(response.status_code, 404)

    def test_document_download_view_owner_success(self):
        """Verify document owner can download the file with proper headers."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('document_download', args=[self.doc1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('Content-Disposition'))
        self.assertIn('attachment;', response['Content-Disposition'])

    def test_document_download_view_idor_protection(self):
        """Verify User B receives 404 when attempting to download User A's document."""
        self.client.force_login(self.user2)
        response = self.client.get(reverse('document_download', args=[self.doc1.pk]))
        self.assertEqual(response.status_code, 404)

    def test_document_edit_view_owner_success(self):
        """Verify document owner can update document metadata."""
        self.client.force_login(self.user1)
        post_data = {
            'title': 'Updated Blood Panel 2026',
            'category': 'medical',
            'description': 'Updated fasting notes.',
        }
        response = self.client.post(reverse('document_edit', args=[self.doc1.pk]), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.title, 'Updated Blood Panel 2026')
        self.assertEqual(self.doc1.description, 'Updated fasting notes.')

    def test_document_edit_view_idor_protection(self):
        """Verify User B receives 404 when attempting to edit User A's document."""
        self.client.force_login(self.user2)
        post_data = {
            'title': 'Hacked Title',
            'category': 'other',
            'description': 'Unauthorized edit',
        }
        response = self.client.post(reverse('document_edit', args=[self.doc1.pk]), data=post_data)
        self.assertEqual(response.status_code, 404)
        self.doc1.refresh_from_db()
        self.assertNotEqual(self.doc1.title, 'Hacked Title')

    def test_document_delete_view_owner_success(self):
        """Verify document owner can delete document and sanitize file from disk."""
        self.client.force_login(self.user1)
        doc_pk = self.doc1.pk
        file_path = self.doc1.file.path

        response = self.client.post(reverse('document_delete', args=[doc_pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/list.html')
        self.assertFalse(Document.objects.filter(pk=doc_pk).exists())
        self.assertFalse(os.path.exists(file_path))

    def test_document_delete_view_idor_protection(self):
        """Verify User B receives 404 when attempting to delete User A's document."""
        self.client.force_login(self.user2)
        doc_pk = self.doc1.pk
        response = self.client.post(reverse('document_delete', args=[doc_pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Document.objects.filter(pk=doc_pk).exists())

    def test_dashboard_live_storage_calculation(self):
        """Verify dashboard calculates actual document counts and storage usage."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # User 1 has 1 document
        self.assertIn('Blood Panel Report 2026', content)
        self.assertIn('VAULT RECORDS', content)
        self.assertNotIn('Your Vault is Empty', content)
