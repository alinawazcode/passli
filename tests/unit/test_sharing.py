import io
import uuid
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.urls import reverse

from documents.models import Document
from sharing.models import SharePass
from sharing.forms import SharePassCreateForm
from sharing.utils import (
    generate_share_key,
    generate_qr_data_uri,
    generate_qr_image_buffer,
    KEY_CHARSET,
)

from tests.unit import get_test_password

User = get_user_model()


class SharePassModelTests(TestCase):
    """Unit tests for the SharePass domain model and cryptographic hashing."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(username='alice', password=self.password)
        self.doc1 = Document.objects.create(
            user=self.user,
            title='Blood Panel Lab.pdf',
            category='medical',
            file=SimpleUploadedFile('blood.pdf', b'%PDF-1.4 mock blood test content', content_type='application/pdf')
        )
        self.doc2 = Document.objects.create(
            user=self.user,
            title='Driver License.png',
            category='personal',
            file=SimpleUploadedFile('license.png', b'\x89PNG mock license content', content_type='image/png')
        )

    def test_share_pass_creation_and_defaults(self):
        """Verify SharePass UUID primary key, defaults, and relationships."""
        expires = timezone.now() + timedelta(minutes=30)
        share_pass = SharePass.objects.create(
            owner=self.user,
            title='Clinic Consult',
            expires_at=expires
        )
        share_pass.documents.add(self.doc1, self.doc2)
        raw_key = '8K7P-42XM'
        share_pass.set_key(raw_key)
        share_pass.save()

        self.assertIsInstance(share_pass.id, uuid.UUID)
        self.assertEqual(share_pass.owner, self.user)
        self.assertEqual(share_pass.title, 'Clinic Consult')
        self.assertTrue(share_pass.can_view)
        self.assertFalse(share_pass.can_download)
        self.assertFalse(share_pass.is_revoked)
        self.assertEqual(share_pass.access_count, 0)
        self.assertEqual(share_pass.max_uses, 0)
        self.assertEqual(share_pass.documents.count(), 2)
        self.assertIn('Clinic Consult', str(share_pass))
        self.assertTrue(share_pass.is_active())
        self.assertFalse(share_pass.is_expired())

    def test_share_key_generation_and_charset(self):
        """Ensure generated Share Keys adhere to format and character set constraints."""
        for _ in range(50):
            key = generate_share_key()
            self.assertEqual(len(key), 9)  # 4 chars + hyphen + 4 chars
            self.assertEqual(key[4], '-')
            parts = key.split('-')
            self.assertEqual(len(parts), 2)
            for part in parts:
                self.assertEqual(len(part), 4)
                for char in part:
                    self.assertIn(char, KEY_CHARSET)
                    self.assertNotIn(char, ['0', 'O', '1', 'I', 'L'])

    def test_key_hashing_and_verification(self):
        """Verify PBKDF2 key hashing, exact match, unhyphenated match, and case normalization."""
        share_pass = SharePass.objects.create(
            owner=self.user,
            title='Verification Test',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        raw_key = 'ABCD-EF23'
        share_pass.set_key(raw_key)
        share_pass.save()

        # Plaintext must not be stored in key_hash
        self.assertNotEqual(share_pass.key_hash, raw_key)
        self.assertTrue(share_pass.key_hash.startswith('pbkdf2_sha256$') or share_pass.key_hash.startswith('argon2'))

        # Exact match
        self.assertTrue(share_pass.verify_key('ABCD-EF23'))
        # Lowercase should verify due to normalization
        self.assertTrue(share_pass.verify_key('abcd-ef23'))
        # Unhyphenated entry should verify
        self.assertTrue(share_pass.verify_key('ABCDEF23'))
        self.assertTrue(share_pass.verify_key('abcdef23'))
        # Invalid keys
        self.assertFalse(share_pass.verify_key('WRONG-KEY'))
        self.assertFalse(share_pass.verify_key(''))
        self.assertFalse(share_pass.verify_key(None))

    def test_expiration_and_revocation_logic(self):
        """Verify expiration timestamp, max uses limit, and revocation behavior."""
        now = timezone.now()
        # Expired by time
        expired_pass = SharePass.objects.create(
            owner=self.user,
            expires_at=now - timedelta(minutes=5)
        )
        self.assertTrue(expired_pass.is_expired())
        self.assertFalse(expired_pass.is_active())
        self.assertEqual(expired_pass.status_label, 'Expired')
        self.assertEqual(expired_pass.time_remaining_seconds, 0)

        # Active pass
        active_pass = SharePass.objects.create(
            owner=self.user,
            expires_at=now + timedelta(minutes=15)
        )
        self.assertFalse(active_pass.is_expired())
        self.assertTrue(active_pass.is_active())
        self.assertEqual(active_pass.status_label, 'Active')
        self.assertGreater(active_pass.time_remaining_seconds, 0)

        # Max uses expiration
        one_time_pass = SharePass.objects.create(
            owner=self.user,
            expires_at=now + timedelta(minutes=30),
            max_uses=1,
            access_count=1
        )
        self.assertTrue(one_time_pass.is_expired())
        self.assertFalse(one_time_pass.is_active())

        # Revocation
        active_pass.revoke()
        active_pass.refresh_from_db()
        self.assertTrue(active_pass.is_revoked)
        self.assertFalse(active_pass.is_active())
        self.assertEqual(active_pass.status_label, 'Revoked')


class QRUtilityTests(TestCase):
    """Unit tests for dynamic QR code generation."""

    def test_qr_data_uri_and_image_buffer(self):
        url = 'https://passli.local/p/12345678-1234-5678-1234-567812345678/'
        data_uri = generate_qr_data_uri(url)
        self.assertTrue(data_uri.startswith('data:image/png;base64,'))

        buf = generate_qr_image_buffer(url)
        self.assertIsInstance(buf, io.BytesIO)
        content = buf.getvalue()
        # PNG signature check: \x89PNG\r\n\x1a\n
        self.assertTrue(content.startswith(b'\x89PNG\r\n\x1a\n'))


class ShareFormsAndViewsTests(TestCase):
    """Integration tests for SharePass forms, views, and security controls."""

    def setUp(self):
        self.client = Client()
        self.alice_password = get_test_password()
        self.bob_password = get_test_password()
        self.alice = User.objects.create_user(username='alice', password=self.alice_password)
        self.bob = User.objects.create_user(username='bob', password=self.bob_password)

        self.alice_doc1 = Document.objects.create(
            user=self.alice,
            title='Alice Passport.pdf',
            category='personal',
            file=SimpleUploadedFile('passport.pdf', b'%PDF-1.4 mock passport content', content_type='application/pdf')
        )
        self.alice_doc2 = Document.objects.create(
            user=self.alice,
            title='Alice Degree.pdf',
            category='education',
            file=SimpleUploadedFile('degree.pdf', b'%PDF-1.4 mock degree content', content_type='application/pdf')
        )
        self.bob_doc = Document.objects.create(
            user=self.bob,
            title='Bob Tax.pdf',
            category='professional',
            file=SimpleUploadedFile('tax.pdf', b'%PDF-1.4 mock tax return', content_type='application/pdf')
        )

    def test_share_create_requires_login(self):
        """Unauthenticated requests to share creation must redirect to login."""
        response = self.client.get(reverse('share_create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_share_create_get_renders_user_documents_only(self):
        """GET /share/create/ must only render documents belonging to the logged-in user."""
        self.client.login(username='alice', password=self.alice_password)
        response = self.client.get(reverse('share_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice Passport.pdf')
        self.assertContains(response, 'Alice Degree.pdf')
        self.assertNotContains(response, 'Bob Tax.pdf')

    def test_share_create_post_success(self):
        """POST /share/create/ with valid documents creates pass and redirects to detail."""
        self.client.login(username='alice', password=self.alice_password)
        post_data = {
            'title': 'Doctor Appointment Pass',
            'documents': [self.alice_doc1.id, self.alice_doc2.id],
            'expires_in': '1h',
            'can_download': True,
        }
        response = self.client.post(reverse('share_create'), post_data)
        self.assertEqual(response.status_code, 302)

        share_pass = SharePass.objects.filter(owner=self.alice, title='Doctor Appointment Pass').first()
        self.assertIsNotNone(share_pass)
        self.assertTrue(share_pass.can_download)
        self.assertEqual(share_pass.documents.count(), 2)

        # Verify redirect to detail
        expected_url = reverse('share_detail', kwargs={'pass_id': share_pass.id})
        self.assertEqual(response.url, expected_url)

        # Verify raw key was placed into session
        raw_key = self.client.session.get(f'new_pass_key_{share_pass.id}')
        self.assertIsNotNone(raw_key)
        self.assertTrue(share_pass.verify_key(raw_key))

    def test_share_create_post_no_documents_rejected(self):
        """POST /share/create/ without documents fails validation."""
        self.client.login(username='alice', password=self.alice_password)
        post_data = {
            'title': 'Empty Pass',
            'documents': [],
            'expires_in': '30m',
        }
        response = self.client.post(reverse('share_create'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please select at least one document')

    def test_share_create_idor_foreign_document_rejected(self):
        """Attempting to bundle another user's document into a Share Pass must be rejected."""
        self.client.login(username='alice', password=self.alice_password)
        post_data = {
            'title': 'Exploit Pass',
            'documents': [self.bob_doc.id],
            'expires_in': '30m',
        }
        response = self.client.post(reverse('share_create'), post_data)
        self.assertEqual(response.status_code, 200)
        # Form should reject foreign document
        self.assertEqual(SharePass.objects.filter(title='Exploit Pass').count(), 0)

    def test_share_detail_view_owner_access(self):
        """Owner can view the pass details, QR code, and attached records."""
        share_pass = SharePass.objects.create(
            owner=self.alice,
            title='Cardiology Review',
            expires_at=timezone.now() + timedelta(hours=2)
        )
        share_pass.documents.add(self.alice_doc1)
        share_pass.set_key('1234-5678')
        share_pass.save()

        self.client.login(username='alice', password=self.alice_password)
        response = self.client.get(reverse('share_detail', kwargs={'pass_id': share_pass.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cardiology Review')
        self.assertContains(response, 'Alice Passport.pdf')
        self.assertContains(response, 'data:image/png;base64,')

    def test_share_detail_view_idor_protection(self):
        """Bob cannot access Alice's Share Pass management view (must return 404)."""
        share_pass = SharePass.objects.create(
            owner=self.alice,
            title='Secret Alice Pass',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.client.login(username='bob', password=self.bob_password)
        response = self.client.get(reverse('share_detail', kwargs={'pass_id': share_pass.id}))
        self.assertEqual(response.status_code, 404)

    def test_share_list_view(self):
        """Share list view displays all passes for the owner and metrics."""
        SharePass.objects.create(
            owner=self.alice,
            title='Pass 1',
            expires_at=timezone.now() + timedelta(minutes=30)
        )
        SharePass.objects.create(
            owner=self.alice,
            title='Pass 2',
            expires_at=timezone.now() - timedelta(minutes=10)
        )

        self.client.login(username='alice', password=self.alice_password)
        response = self.client.get(reverse('share_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pass 1')
        self.assertContains(response, 'Pass 2')
        self.assertEqual(response.context['total_count'], 2)
        self.assertEqual(response.context['active_count'], 1)
        self.assertEqual(response.context['expired_count'], 1)

    def test_share_revoke_view_owner_success(self):
        """Owner can immediately revoke an active pass via POST."""
        share_pass = SharePass.objects.create(
            owner=self.alice,
            title='Revoke Test',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.client.login(username='alice', password=self.alice_password)
        response = self.client.post(reverse('share_revoke', kwargs={'pass_id': share_pass.id}))
        self.assertEqual(response.status_code, 302)

        share_pass.refresh_from_db()
        self.assertTrue(share_pass.is_revoked)
        self.assertFalse(share_pass.is_active())

    def test_share_revoke_view_idor_protection(self):
        """Bob cannot revoke Alice's Share Pass."""
        share_pass = SharePass.objects.create(
            owner=self.alice,
            title='Protected Alice Pass',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.client.login(username='bob', password=self.bob_password)
        response = self.client.post(reverse('share_revoke', kwargs={'pass_id': share_pass.id}))
        self.assertEqual(response.status_code, 404)
        share_pass.refresh_from_db()
        self.assertFalse(share_pass.is_revoked)

    def test_share_qr_download_view(self):
        """Owner can download QR code PNG attachment."""
        share_pass = SharePass.objects.create(
            owner=self.alice,
            title='QR Download Test',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.client.login(username='alice', password=self.alice_password)
        response = self.client.get(reverse('share_qr_download', kwargs={'pass_id': share_pass.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(response.getvalue().startswith(b'\x89PNG\r\n\x1a\n'))
