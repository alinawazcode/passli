"""
AES-256-GCM Vault Encryption & Storage Security Test Suite
Validates:
- Cryptographic primitives (encrypt_bytes, decrypt_bytes, nonces, HKDF derivation)
- Tamper resistance and authentication tag validation (VaultDecryptionError)
- Transparent model encryption on upload and legacy dual-mode fallback
- In-memory decrypted streaming for owner previews and downloads
- In-memory decrypted streaming for verified recipient Share Pass access
- Database migration management command (encrypt_vault_storage)
"""

import io
import os
import hashlib
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from tests.unit import get_test_password

from documents.models import Document
from documents.services.crypto_service import (
    encrypt_bytes,
    decrypt_bytes,
    get_vault_master_key,
    generate_vault_master_key,
    validate_vault_master_key,
    VaultDecryptionError,
)
from sharing.models import SharePass
from sharing.utils import generate_share_key

User = get_user_model()


class CryptoServiceUnitTests(TestCase):
    """Unit tests for low-level cryptographic functions in crypto_service."""

    def test_encrypt_decrypt_roundtrip(self):
        """Plaintext encrypted with encrypt_bytes must decrypt identically with decrypt_bytes."""
        plaintext = b"Highly confidential healthcare diagnosis payload 2026."
        ciphertext = encrypt_bytes(plaintext)

        # Ciphertext format: 12-byte nonce + (len(plaintext)) ciphertext + 16-byte tag
        self.assertEqual(len(ciphertext), len(plaintext) + 28)
        self.assertNotEqual(ciphertext, plaintext)

        decrypted = decrypt_bytes(ciphertext)
        self.assertEqual(decrypted, plaintext)

    def test_empty_payload_encryption(self):
        """Empty plaintext should encrypt to exactly 28 bytes (nonce + tag) and decrypt to empty bytes."""
        empty_plain = b""
        ciphertext = encrypt_bytes(empty_plain)
        self.assertEqual(len(ciphertext), 28)
        self.assertEqual(decrypt_bytes(ciphertext), empty_plain)

    def test_unique_nonce_per_encryption(self):
        """Encrypting identical plaintext twice must produce different ciphertexts due to CSPRNG nonces."""
        plaintext = b"Same static password or secret token."
        c1 = encrypt_bytes(plaintext)
        c2 = encrypt_bytes(plaintext)
        self.assertNotEqual(c1, c2)
        # Nonces (first 12 bytes) must differ
        self.assertNotEqual(c1[:12], c2[:12])
        # Both must decrypt to original
        self.assertEqual(decrypt_bytes(c1), plaintext)
        self.assertEqual(decrypt_bytes(c2), plaintext)

    def test_tamper_detection_single_byte_mutation(self):
        """Tampering with any byte of the ciphertext or tag must raise VaultDecryptionError."""
        plaintext = b"Critical financial statement."
        ciphertext = bytearray(encrypt_bytes(plaintext))

        # Flip a bit in the ciphertext payload
        ciphertext[15] ^= 0x01

        with self.assertRaises(VaultDecryptionError):
            decrypt_bytes(bytes(ciphertext))

    def test_tamper_detection_truncated_payload(self):
        """Payloads shorter than the 28-byte nonce+tag minimum must raise VaultDecryptionError."""
        with self.assertRaises(VaultDecryptionError):
            decrypt_bytes(b"too_short")

    def test_generate_vault_master_key(self):
        """generate_vault_master_key must return a 64-char hex string (32 bytes)."""
        key_hex = generate_vault_master_key()
        self.assertEqual(len(key_hex), 64)
        raw_key = bytes.fromhex(key_hex)
        self.assertEqual(len(raw_key), 32)

    def test_deterministic_hkdf_fallback_without_env(self):
        """When VAULT_MASTER_KEY is unset in DEBUG mode, HKDF derivation from SECRET_KEY produces a 32-byte key."""
        with self.settings(DEBUG=True, VAULT_MASTER_KEY=None):
            key = get_vault_master_key()
            self.assertEqual(len(key), 32)
            self.assertIsInstance(key, bytes)

    def test_missing_key_fails_startup_when_debug_false(self):
        """When DEBUG is False, missing VAULT_MASTER_KEY raises ImproperlyConfigured at startup."""
        with self.assertRaises(ImproperlyConfigured):
            validate_vault_master_key(debug=False, key=None)

    def test_invalid_length_key_fails_startup_when_debug_false(self):
        """When DEBUG is False, a key not exactly 32 bytes (hex or base64) raises ImproperlyConfigured."""
        # Too short (16 hex chars = 8 bytes)
        with self.assertRaises(ImproperlyConfigured):
            validate_vault_master_key(debug=False, key="0123456789abcdef")

        # Invalid random string
        with self.assertRaises(ImproperlyConfigured):
            validate_vault_master_key(debug=False, key="not-a-32-byte-hex-or-base64-key")

    def test_roundtrip_with_aad(self):
        """Plaintext encrypted with associated data (AAD) requires identical AAD to decrypt."""
        plaintext = b"Sensitive AAD test record."
        aad = b"doc-uuid-12345-67890"

        ciphertext = encrypt_bytes(plaintext, associated_data=aad)
        decrypted = decrypt_bytes(ciphertext, associated_data=aad)
        self.assertEqual(decrypted, plaintext)

    def test_tampered_byte_fails_decryption(self):
        """Tampering with a single byte in ciphertext must fail authentication and raise VaultDecryptionError."""
        plaintext = b"Integrity verification payload."
        aad = b"doc-uuid-aad-999"
        ciphertext = bytearray(encrypt_bytes(plaintext, associated_data=aad))

        # Mutate payload
        ciphertext[20] ^= 0x55
        with self.assertRaises(VaultDecryptionError):
            decrypt_bytes(bytes(ciphertext), associated_data=aad)

    def test_wrong_aad_fails_decryption(self):
        """Attempting to decrypt ciphertext with a mismatched AAD raises VaultDecryptionError."""
        plaintext = b"Document content bound to UUID A."
        aad_a = b"uuid-document-alpha"
        aad_b = b"uuid-document-bravo"

        ciphertext = encrypt_bytes(plaintext, associated_data=aad_a)

        # Decrypting with wrong AAD (and allow_legacy=False) must fail
        with self.assertRaises(VaultDecryptionError):
            decrypt_bytes(ciphertext, associated_data=aad_b, allow_legacy=False)


class DocumentModelVaultEncryptionTests(TestCase):
    """Tests covering Document model encryption lifecycle, metadata updates, and fallback."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="crypto_owner",
            email="crypto@passli.dev",
            password=self.password
        )
        self.raw_content = b"%PDF-1.4 Vault Encrypted Test Document Content"
        self.file = SimpleUploadedFile(
            "Encrypted_Test.pdf",
            self.raw_content,
            content_type="application/pdf"
        )
        self.doc = Document.objects.create(
            user=self.user,
            title="Medical Test Doc",
            category="medical",
            file=self.file
        )

    def tearDown(self):
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    def test_document_stored_encrypted_at_rest(self):
        """Physical file on disk must be encrypted and contain AES-256-GCM payload."""
        self.assertTrue(self.doc.is_encrypted)
        self.assertEqual(self.doc.file_size, len(self.raw_content))
        self.assertEqual(self.doc.file_hash, hashlib.sha256(self.raw_content).hexdigest())

        # Inspect disk bytes directly
        with open(self.doc.file.path, 'rb') as f:
            disk_bytes = f.read()

        # Disk bytes must not match raw content
        self.assertNotEqual(disk_bytes, self.raw_content)
        # Disk bytes must be 28 bytes larger (12-byte nonce + 16-byte tag)
        self.assertEqual(len(disk_bytes), len(self.raw_content) + 28)

        # get_decrypted_content() must return the original plaintext
        self.assertEqual(self.doc.get_decrypted_content(), self.raw_content)

    def test_document_metadata_update_does_not_reencrypt(self):
        """Updating title or description must not re-encrypt or corrupt the stored file."""
        with open(self.doc.file.path, 'rb') as f:
            original_disk_bytes = f.read()

        self.doc.title = "Updated Medical Title"
        self.doc.description = "Updated description"
        self.doc.save()

        with open(self.doc.file.path, 'rb') as f:
            new_disk_bytes = f.read()

        # Disk payload must remain identical
        self.assertEqual(original_disk_bytes, new_disk_bytes)
        # Decryption must still succeed
        self.assertEqual(self.doc.get_decrypted_content(), self.raw_content)

    def test_legacy_unencrypted_document_fallback(self):
        """A document marked is_encrypted=False must be read as raw bytes without errors."""
        legacy_content = b"Unencrypted legacy file content from 2025."
        legacy_file = SimpleUploadedFile("legacy.txt", legacy_content, content_type="text/plain")

        # Bypass save encryption by creating with raw save
        legacy_doc = Document(
            user=self.user,
            title="Legacy Document",
            category="other",
            file=legacy_file,
            is_encrypted=False
        )
        # Save without encryption logic
        super(Document, legacy_doc).save()
        # Ensure is_encrypted is False in db
        Document.objects.filter(id=legacy_doc.id).update(is_encrypted=False)
        legacy_doc.refresh_from_db()

        self.assertFalse(legacy_doc.is_encrypted)
        # get_decrypted_content should return legacy content directly
        self.assertEqual(legacy_doc.get_decrypted_content(), legacy_content)

    def test_corrupted_disk_file_raises_vault_decryption_error(self):
        """If physical file on disk is altered, get_decrypted_content must raise VaultDecryptionError."""
        # Mutate the file on disk
        with open(self.doc.file.path, 'r+b') as f:
            f.seek(18)
            f.write(b'\xFF\xFF')

        with self.assertRaises(VaultDecryptionError):
            self.doc.get_decrypted_content()

    def test_moved_ciphertext_to_another_document_fails_to_decrypt(self):
        """
        A ciphertext moved to another document fails to decrypt because AES-GCM
        binds the document's unique UUID as Associated Data (AAD).
        """
        # Create a second document
        other_content = b"%PDF-1.4 Second Document Original Content"
        other_file = SimpleUploadedFile("Doc2.pdf", other_content, content_type="application/pdf")
        doc2 = Document.objects.create(
            user=self.user,
            title="Second Document",
            category="personal",
            file=other_file
        )

        # Overwrite doc2's file on disk with doc1's ciphertext
        with open(self.doc.file.path, 'rb') as f:
            doc1_ciphertext = f.read()

        with open(doc2.file.path, 'wb') as f:
            f.write(doc1_ciphertext)

        # Attempting to decrypt doc2 should fail because doc2.uuid does not match doc1.uuid
        with self.assertRaises(VaultDecryptionError):
            doc2.get_decrypted_content()

    def test_key_rotation_with_previous_key_works(self):
        """
        A document encrypted with an older key version decrypts successfully when
        VAULT_MASTER_KEY_PREVIOUS is configured.
        """
        old_key = generate_vault_master_key()
        new_key = generate_vault_master_key()

        # Doc was saved under key version 1 with old_key
        with self.settings(
            VAULT_KEY_VERSION=1,
            VAULT_MASTER_KEY=old_key,
            VAULT_MASTER_KEY_PREVIOUS=None,
            DEBUG=False
        ):
            doc = Document.objects.create(
                user=self.user,
                title="Rotation Test Doc",
                category="other",
                file=SimpleUploadedFile("rotate.txt", b"Secret payload before rotation.", content_type="text/plain")
            )
            self.assertEqual(doc.key_version, 1)
            self.assertEqual(doc.get_decrypted_content(), b"Secret payload before rotation.")

        # Key rotation: bump version to 2, new key as active, old key as previous
        with self.settings(
            VAULT_KEY_VERSION=2,
            VAULT_MASTER_KEY=new_key,
            VAULT_MASTER_KEY_PREVIOUS=old_key,
            DEBUG=False
        ):
            # Reading old document uses VAULT_MASTER_KEY_PREVIOUS and succeeds!
            self.assertEqual(doc.get_decrypted_content(), b"Secret payload before rotation.")


class VaultStreamingViewsTests(TestCase):
    """Tests covering decrypted streaming in document views and recipient views."""

    def setUp(self):
        self.client = Client()
        self.password = get_test_password()
        self.owner = User.objects.create_user(
            username="doc_stream_owner",
            email="owner@passli.dev",
            password=self.password
        )
        self.other_user = User.objects.create_user(
            username="doc_other_user",
            email="other@passli.dev",
            password=self.password
        )

        self.plaintext = b"%PDF-1.4 High Security Document Payload"
        self.file = SimpleUploadedFile("Secure_Doc.pdf", self.plaintext, content_type="application/pdf")
        self.doc = Document.objects.create(
            user=self.owner,
            title="Confidential Report",
            category="financial",
            file=self.file
        )

        # Create SharePass with doc attached
        self.plain_key = "SECKEY99"
        self.share_pass = SharePass.objects.create(
            owner=self.owner,
            title="Audit Review Pass",
            expires_at=timezone.now() + timedelta(hours=2),
            max_uses=10,
            can_download=True
        )
        self.share_pass.set_key(self.plain_key)
        self.share_pass.save()
        self.share_pass.documents.add(self.doc)

    def tearDown(self):
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    def test_owner_preview_serves_decrypted_content(self):
        """Document owner preview must stream in-memory decrypted content with security headers."""
        self.client.force_login(self.owner)
        response = self.client.get(reverse('document_preview', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.plaintext)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', response['Cache-Control'])

    def test_owner_download_serves_decrypted_content(self):
        """Document owner download must stream in-memory decrypted content as attachment."""
        self.client.force_login(self.owner)
        response = self.client.get(reverse('document_download', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.plaintext)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_recipient_preview_serves_decrypted_content(self):
        """Verified recipient with valid session must receive decrypted stream."""
        session = self.client.session
        session[f"recipient_authenticated_{str(self.share_pass.id)}"] = True
        session.save()

        response = self.client.get(
            reverse('recipient_doc_preview', args=[self.share_pass.id, self.doc.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.plaintext)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', response['Cache-Control'])

    def test_recipient_download_serves_decrypted_content(self):
        """Verified recipient with can_download=True must receive decrypted download stream."""
        session = self.client.session
        session[f"recipient_authenticated_{str(self.share_pass.id)}"] = True
        session.save()

        response = self.client.get(
            reverse('recipient_doc_download', args=[self.share_pass.id, self.doc.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.plaintext)
        self.assertIn('attachment;', response['Content-Disposition'])

    def test_corrupted_document_preview_returns_404(self):
        """If ciphertext is corrupted on disk, preview view must cleanly return 404."""
        self.client.force_login(self.owner)
        # Corrupt file on disk
        with open(self.doc.file.path, 'r+b') as f:
            f.seek(10)
            f.write(b'\x00\x00\x00')

        response = self.client.get(reverse('document_preview', args=[self.doc.pk]))
        self.assertEqual(response.status_code, 404)


class EncryptVaultStorageCommandTests(TestCase):
    """Tests covering the encrypt_vault_storage migration management command."""

    def setUp(self):
        self.password = get_test_password()
        self.user = User.objects.create_user(
            username="mig_owner",
            email="mig@passli.dev",
            password=self.password
        )
        self.raw_content = b"Unencrypted legacy record for migration testing."
        raw_file = SimpleUploadedFile("legacy_mig.txt", self.raw_content, content_type="text/plain")

        self.legacy_doc = Document(
            user=self.user,
            title="Legacy Unencrypted Record",
            category="other",
            file=raw_file,
            is_encrypted=False,
            file_hash=hashlib.sha256(self.raw_content).hexdigest(),
            file_size=len(self.raw_content)
        )
        super(Document, self.legacy_doc).save()
        Document.objects.filter(id=self.legacy_doc.id).update(is_encrypted=False)
        self.legacy_doc.refresh_from_db()

    def tearDown(self):
        for doc in Document.objects.all():
            if doc.file and os.path.exists(doc.file.path):
                try:
                    os.remove(doc.file.path)
                except OSError:
                    pass

    def test_command_dry_run_does_not_modify_file_or_db(self):
        """Dry-run must report planned migration without altering database or disk files."""
        out = io.StringIO()
        call_command('encrypt_vault_storage', '--dry-run', stdout=out)
        output = out.getvalue()

        self.assertIn('DRY-RUN', output)
        self.assertIn('Would encrypt', output)

        self.legacy_doc.refresh_from_db()
        self.assertFalse(self.legacy_doc.is_encrypted)

        # File on disk must remain unencrypted
        with open(self.legacy_doc.file.path, 'rb') as f:
            self.assertEqual(f.read(), self.raw_content)

    def test_command_live_execution_encrypts_storage(self):
        """Live run must encrypt disk file with AES-256-GCM and set is_encrypted=True."""
        out = io.StringIO()
        call_command('encrypt_vault_storage', stdout=out)
        output = out.getvalue()

        self.assertIn('Encryption at rest completed successfully', output)

        self.legacy_doc.refresh_from_db()
        self.assertTrue(self.legacy_doc.is_encrypted)

        # Disk file must be encrypted (28 bytes overhead)
        with open(self.legacy_doc.file.path, 'rb') as f:
            disk_bytes = f.read()
        self.assertEqual(len(disk_bytes), len(self.raw_content) + 28)
        self.assertNotEqual(disk_bytes, self.raw_content)

        # Decryption must recover original content
        self.assertEqual(self.legacy_doc.get_decrypted_content(), self.raw_content)

    def test_command_reencrypt_legacy_with_aad(self):
        """--reencrypt-legacy option decrypts legacy ciphertext and re-encrypts with document UUID as AAD."""
        # Prepare legacy encrypted file (encrypted without AAD)
        legacy_ciphertext = encrypt_bytes(self.raw_content, associated_data=None)
        with open(self.legacy_doc.file.path, 'wb') as f:
            f.write(legacy_ciphertext)
        self.legacy_doc.is_encrypted = True
        self.legacy_doc.save(update_fields=['is_encrypted'])

        out = io.StringIO()
        call_command('encrypt_vault_storage', '--reencrypt-legacy', stdout=out)
        output = out.getvalue()

        self.assertIn('legacy encrypted document(s) to re-encrypt', output)
        self.assertIn('Successfully re-encrypted with UUID AAD', output)

        self.legacy_doc.refresh_from_db()
        self.assertTrue(self.legacy_doc.is_encrypted)
        self.assertEqual(self.legacy_doc.get_decrypted_content(), self.raw_content)
