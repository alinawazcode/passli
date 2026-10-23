"""
Comprehensive Security & Vulnerability Test Suite
Tests OWASP Top 10 vulnerabilities, IDOR prevention, upload sanitization,
path traversal defense, CSRF enforcement, and cryptographic checksum validation.
"""

import os
import hashlib
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from documents.models import Document
from documents.forms import DocumentUploadForm

from tests.unit import get_test_password

User = get_user_model()


class SecurityAndVulnerabilityTests(TestCase):
    """Security audit tests verifying Passli defensive posture."""

    def setUp(self):
        self.client_alice = Client()
        self.client_bob = Client()

        self.alice_password = get_test_password()
        self.bob_password = get_test_password()

        self.alice = User.objects.create_user(
            username="alice_security",
            email="alice@passli.dev",
            password=self.alice_password
        )
        self.bob = User.objects.create_user(
            username="bob_security",
            email="bob@passli.dev",
            password=self.bob_password
        )

        self.client_alice.force_login(self.alice)
        self.client_bob.force_login(self.bob)

        # Alice's sensitive medical document
        self.alice_doc = Document.objects.create(
            user=self.alice,
            title="Alice_Confidential_Medical_History.pdf",
            category="medical",
            description="Private medical history record.",
            file=SimpleUploadedFile("alice_med.pdf", b"%PDF-1.4 confidential patient records", content_type="application/pdf")
        )

    def tearDown(self):
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    # -------------------------------------------------------------
    # 1. IDOR (Insecure Direct Object Reference) Protection Tests
    # -------------------------------------------------------------
    def test_idor_prevention_on_detail_view(self):
        """Verify Bob cannot view Alice's document detail page."""
        response = self.client_bob.get(reverse('document_detail', args=[self.alice_doc.pk]))
        self.assertEqual(response.status_code, 404)

    def test_idor_prevention_on_download_view(self):
        """Verify Bob cannot download Alice's document file."""
        response = self.client_bob.get(reverse('document_download', args=[self.alice_doc.pk]))
        self.assertEqual(response.status_code, 404)

    def test_idor_prevention_on_edit_view(self):
        """Verify Bob cannot edit or overwrite Alice's document metadata."""
        post_data = {
            'title': 'Hacked by Bob',
            'category': 'other',
            'description': 'Malicious modification',
        }
        response = self.client_bob.post(reverse('document_edit', args=[self.alice_doc.pk]), data=post_data)
        self.assertEqual(response.status_code, 404)
        self.alice_doc.refresh_from_db()
        self.assertEqual(self.alice_doc.title, "Alice_Confidential_Medical_History.pdf")

    def test_idor_prevention_on_delete_view(self):
        """Verify Bob cannot delete Alice's document."""
        response = self.client_bob.post(reverse('document_delete', args=[self.alice_doc.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Document.objects.filter(pk=self.alice_doc.pk).exists())

    # -------------------------------------------------------------
    # 2. Authentication & Authorization Enforcement
    # -------------------------------------------------------------
    def test_unauthenticated_protected_route_redirects(self):
        """Verify unauthenticated requests to protected endpoints redirect to login."""
        anon_client = Client()
        protected_urls = [
            reverse('dashboard'),
            reverse('documents_list'),
            reverse('documents_upload'),
            reverse('document_detail', args=[self.alice_doc.pk]),
            reverse('document_download', args=[self.alice_doc.pk]),
            reverse('document_edit', args=[self.alice_doc.pk]),
            reverse('document_delete', args=[self.alice_doc.pk]),
        ]

        for url in protected_urls:
            response = anon_client.get(url)
            self.assertEqual(response.status_code, 302, f"URL {url} did not redirect anonymous visitor")
            self.assertIn(reverse('login'), response.url)

    # -------------------------------------------------------------
    # 3. Malicious File Upload & Extension Whitelist Defense
    # -------------------------------------------------------------
    def test_executable_upload_blocked(self):
        """Verify .exe, .bat, .sh, .py, .php, .html files are rejected."""
        malicious_extensions = ['.exe', '.bat', '.sh', '.py', '.php', '.html', '.js', '.vbs']
        for ext in malicious_extensions:
            bad_file = SimpleUploadedFile(f"payload{ext}", b"malicious content", content_type="application/octet-stream")
            post_data = {
                'title': f'Malicious {ext}',
                'category': 'other',
                'file': bad_file,
            }
            response = self.client_alice.post(reverse('documents_upload'), data=post_data)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f"Unsupported file format &#x27;{ext}&#x27;.")
            self.assertFalse(Document.objects.filter(title=f'Malicious {ext}').exists())

    def test_oversized_file_upload_blocked(self):
        """Verify files exceeding 25 MB are rejected by DocumentUploadForm."""
        mock_file = SimpleUploadedFile("oversized_scan.pdf", b"%PDF-1.4 header", content_type="application/pdf")
        mock_file.size = 26 * 1024 * 1024  # 26 MB simulated size

        form_data = {
            'title': 'Oversized Scan Report',
            'category': 'medical',
            'description': 'Test oversized upload',
        }
        form = DocumentUploadForm(data=form_data, files={'file': mock_file})
        self.assertFalse(form.is_valid())
        self.assertIn("File size exceeds maximum allowed limit of 25 MB.", form.errors['file'])

    # -------------------------------------------------------------
    # 4. Path Traversal & File System Isolation
    # -------------------------------------------------------------
    def test_path_traversal_filename_sanitization(self):
        """Verify filenames with path traversal characters (../) are sanitized and isolated."""
        traversal_file = SimpleUploadedFile(
            "../../../../etc/shadow.pdf",
            b"%PDF-1.4 simulated traversal",
            content_type="application/pdf"
        )
        post_data = {
            'title': 'Traversal Test',
            'category': 'personal',
            'file': traversal_file,
        }
        response = self.client_alice.post(reverse('documents_upload'), data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        doc = Document.objects.get(title='Traversal Test')
        # Ensure path is safely within vault_files/user_<id>/
        self.assertTrue(doc.file.name.startswith(f"vault_files{os.sep}user_{self.alice.pk}") or doc.file.name.startswith(f"vault_files/user_{self.alice.pk}"))
        self.assertNotIn("..", doc.file.name)

    # -------------------------------------------------------------
    # 5. SHA-256 Cryptographic Checksum Integrity
    # -------------------------------------------------------------
    def test_cryptographic_checksum_matches_payload(self):
        """Verify SHA-256 digest accurately reflects exact binary bytes."""
        binary_payload = b"\x89PNG\r\n\x1a\n cryptographic salt token 992817"
        expected_digest = hashlib.sha256(binary_payload).hexdigest()

        png_file = SimpleUploadedFile("hash_test.png", binary_payload, content_type="image/png")
        doc = Document.objects.create(
            user=self.alice,
            title="Integrity Test Record",
            category="personal",
            file=png_file
        )

        self.assertEqual(doc.file_hash, expected_digest)
        self.assertEqual(len(doc.file_hash), 64)

    # -------------------------------------------------------------
    # 6. Session Security & Logout Invalidation
    # -------------------------------------------------------------
    def test_logout_session_invalidation(self):
        """Verify logout destroys session and prevents subsequent authorized actions."""
        # Alice is logged in
        dash_res = self.client_alice.get(reverse('dashboard'))
        self.assertEqual(dash_res.status_code, 200)

        # Alice logs out
        logout_res = self.client_alice.post(reverse('logout'), follow=True)
        self.assertEqual(logout_res.status_code, 200)

        # Attempting dashboard again redirects
        dash_after_logout = self.client_alice.get(reverse('dashboard'))
        self.assertEqual(dash_after_logout.status_code, 302)
        self.assertIn(reverse('login'), dash_after_logout.url)

    # -------------------------------------------------------------
    # 7. Cross-Site Scripting (XSS) Defense & HTML Auto-Escaping
    # -------------------------------------------------------------
    def test_xss_stored_payload_escaped(self):
        """Verify script tags stored in document titles/descriptions are escaped in rendered HTML."""
        xss_payload = "<script>alert('XSS_ATTACK_VECTOR')</script>"
        doc = Document.objects.create(
            user=self.alice,
            title=f"Medical Record {xss_payload}",
            description=f"Description containing {xss_payload}",
            category="medical",
            file=SimpleUploadedFile("xss_test.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        )

        # List view inspection
        res_list = self.client_alice.get(reverse('documents_list'))
        self.assertEqual(res_list.status_code, 200)
        self.assertNotContains(res_list, "<script>alert('XSS_ATTACK_VECTOR')</script>")
        self.assertContains(res_list, "&lt;script&gt;alert(&#x27;XSS_ATTACK_VECTOR&#x27;)&lt;/script&gt;")

        # Detail view inspection
        res_detail = self.client_alice.get(reverse('document_detail', args=[doc.pk]))
        self.assertEqual(res_detail.status_code, 200)
        self.assertNotContains(res_detail, "<script>alert('XSS_ATTACK_VECTOR')</script>")
        self.assertContains(res_detail, "&lt;script&gt;alert(&#x27;XSS_ATTACK_VECTOR&#x27;)&lt;/script&gt;")

    # -------------------------------------------------------------
    # 8. SQL Injection (SQLi) Defense via ORM Parameterization
    # -------------------------------------------------------------
    def test_sql_injection_defense_on_search_and_filters(self):
        """Verify SQL injection payloads in queries do not break ORM or return unauthorized rows."""
        sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE documents_document; --",
            "1' UNION SELECT username, password FROM auth_user --",
            "admin'--",
            "' OR 1=1 #",
        ]

        for payload in sqli_payloads:
            # Document list search
            res = self.client_bob.get(f"{reverse('documents_list')}?q={payload}&category=all")
            self.assertEqual(res.status_code, 200)
            # Bob must NEVER see Alice's confidential documents
            self.assertNotContains(res, "Alice_Confidential_Medical_History.pdf")

    # -------------------------------------------------------------
    # 9. Cross-Site Request Forgery (CSRF) Enforcement
    # -------------------------------------------------------------
    def test_csrf_protection_enforced_on_mutating_requests(self):
        """Verify unauthenticated/untokened external POST requests are rejected with 403 CSRF failure."""
        csrf_client = Client(enforce_csrf_checks=True)
        # Attempt to post document delete without valid CSRF token
        response = csrf_client.post(reverse('document_delete', args=[self.alice_doc.pk]))
        self.assertEqual(response.status_code, 403)

    # -------------------------------------------------------------
    # 10. Unvalidated Redirect (Open Redirect) Defense
    # -------------------------------------------------------------
    def test_open_redirect_defense_on_login(self):
        """Verify malicious external URLs in 'next' query param are rejected by login redirect."""
        malicious_urls = [
            "https://evil-phishing-site.com",
            "//evil-phishing-site.com",
            "http://attacker.com/steal-creds",
            "javascript:alert(1)",
        ]

        for evil_url in malicious_urls:
            login_res = self.client_bob.post(
                f"{reverse('login')}?next={evil_url}",
                {'username': 'bob_security', 'password': self.bob_password},
                follow=False
            )
            # Must redirect safely to internal dashboard, not the evil target
            self.assertEqual(login_res.status_code, 302)
            self.assertEqual(login_res.url, reverse('dashboard'))

    # -------------------------------------------------------------
    # 11. Superadmin Privilege & Access Restriction (RBAC)
    # -------------------------------------------------------------
    def test_regular_user_cannot_access_superadmin_consoles(self):
        """Verify non-superadmin accounts cannot access custom administrative suites and are redirected."""
        admin_endpoints = [
            reverse('admin_dashboard_overview'),
            reverse('admin_dashboard_users'),
            reverse('admin_dashboard_documents'),
            reverse('admin_dashboard_passes'),
            reverse('admin_dashboard_audit'),
        ]

        for endpoint in admin_endpoints:
            res_alice = self.client_alice.get(endpoint)
            self.assertEqual(res_alice.status_code, 302, f"Endpoint {endpoint} was directly accessible by regular user")
            self.assertIn(reverse('login'), res_alice.url)

    # -------------------------------------------------------------
    # 12. Security Headers & Anti-Caching Enforcement
    # -------------------------------------------------------------
    def test_security_headers_and_anti_caching_on_file_streams(self):
        """Verify document download and preview streams return anti-caching and nosniff headers."""
        preview_res = self.client_alice.get(reverse('document_preview', args=[self.alice_doc.pk]))
        self.assertEqual(preview_res.status_code, 200)
        self.assertEqual(preview_res.headers.get('Cache-Control'), 'no-store, no-cache, must-revalidate, private')
        self.assertEqual(preview_res.headers.get('X-Content-Type-Options'), 'nosniff')

        download_res = self.client_alice.get(reverse('document_download', args=[self.alice_doc.pk]))
        self.assertEqual(download_res.status_code, 200)
        self.assertEqual(download_res.headers.get('Cache-Control'), 'no-store, no-cache, must-revalidate, private')
        self.assertEqual(download_res.headers.get('X-Content-Type-Options'), 'nosniff')

    # -------------------------------------------------------------
    # 13. Server-Side Template Injection (SSTI) Neutrality
    # -------------------------------------------------------------
    def test_ssti_template_syntax_neutrality(self):
        """Verify template syntax payloads ({{ 7*7 }}, {% debug %}) are treated as plain text."""
        ssti_payload = "{{ 7*7 }} {% debug %} {{ request.user.password }}"
        doc = Document.objects.create(
            user=self.alice,
            title=f"Record {ssti_payload}",
            description=f"Desc {ssti_payload}",
            category="medical",
            file=SimpleUploadedFile("ssti.pdf", b"%PDF-1.4 ssti test", content_type="application/pdf")
        )

        res = self.client_alice.get(reverse('document_detail', args=[doc.pk]))
        self.assertEqual(res.status_code, 200)
        # Should not evaluate 7*7 = 49 or dump debug objects
        self.assertNotContains(res, "49")
        self.assertContains(res, "{{ 7*7 }}")

    # -------------------------------------------------------------
    # 14. Zero-Knowledge Cryptographic Key Storage
    # -------------------------------------------------------------
    def test_share_pass_zero_knowledge_key_hashing(self):
        """Verify 8-character plaintext Share Keys are never stored in database or plaintext fields."""
        from datetime import timedelta
        from django.utils import timezone
        from sharing.models import SharePass
        from sharing.utils import generate_share_key

        raw_key = generate_share_key()

        share_pass = SharePass(
            owner=self.alice,
            title="ZK Cryptographic Test Pass",
            expires_at=timezone.now() + timedelta(minutes=30)
        )
        share_pass.set_key(raw_key)
        share_pass.save()
        share_pass.documents.add(self.alice_doc)

        # Refresh from database and assert raw key is not present in stored hash
        share_pass.refresh_from_db()
        self.assertTrue(share_pass.key_hash.startswith("pbkdf2_sha256$"))
        self.assertNotIn(raw_key, share_pass.key_hash)
        self.assertTrue(share_pass.verify_key(raw_key))
        self.assertFalse(share_pass.verify_key("WRONG-KEY"))

