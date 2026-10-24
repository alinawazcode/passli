import os
import uuid
import hashlib
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from .services.crypto_service import encrypt_bytes, decrypt_bytes, VaultDecryptionError

logger = logging.getLogger(__name__)
User = get_user_model()


def document_upload_path(instance, filename):
    """
    Generates a secure, sanitized, user-isolated file path.
    Always uses POSIX forward slashes for cross-platform compatibility (Windows & Linux/Unix).
    Format: vault_files/user_<id>/<uuid>.<ext>
    """
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    user_id = instance.user_id if instance.user_id else 'anon'
    return f"vault_files/user_{user_id}/{unique_name}"


class Document(models.Model):
    """
    Encrypted Personal Vault Document record.
    Stores metadata, domain classification, MIME type, file size, and SHA-256 integrity checksum.
    """

    CATEGORY_CHOICES = [
        ('medical', 'Medical Records'),
        ('education', 'Education & Degrees'),
        ('vehicle', 'Vehicle & Asset'),
        ('personal', 'Personal & Identity'),
        ('professional', 'Professional & Employment'),
        ('other', 'Other Records'),
    ]

    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Document UUID'
    )
    key_version = models.PositiveIntegerField(
        default=1,
        help_text='Vault encryption key version used for this document'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Vault Owner'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Document Title'
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name='Category Domain'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Description / Notes'
    )
    file = models.FileField(
        upload_to=document_upload_path,
        verbose_name='Vault File'
    )
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Original Filename'
    )
    file_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='MIME / Content Type'
    )
    file_size = models.BigIntegerField(
        default=0,
        verbose_name='File Size (Bytes)'
    )
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='SHA-256 Checksum'
    )
    is_encrypted = models.BooleanField(
        default=True,
        verbose_name='Encrypted at Rest',
        help_text='Indicates if file content is stored with AES-256-GCM authenticated encryption.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'category']),
            models.Index(fields=['user', 'created_at']),
        ]
        verbose_name = 'Vault Document'
        verbose_name_plural = 'Vault Documents'

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"

    def save(self, *args, **kwargs):
        """Compute SHA-256 checksum and encrypt file content with AES-256-GCM before saving."""
        from django.conf import settings

        if not self.uuid:
            self.uuid = uuid.uuid4()

        if self.file and hasattr(self.file, 'name'):
            # Record original filename if not already set
            if not self.original_filename:
                self.original_filename = os.path.basename(self.file.name)

            # Detect content type from extension if empty
            if not self.file_type and self.original_filename:
                ext = os.path.splitext(self.original_filename)[1].lower()
                mime_map = {
                    '.pdf': 'application/pdf',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                }
                self.file_type = mime_map.get(ext, 'application/octet-stream')

            # Check if this is an uncommitted (newly uploaded or modified) file object
            is_uncommitted = not getattr(self.file, '_committed', True) or getattr(self, '_force_encrypt', False)
            if is_uncommitted:
                try:
                    if hasattr(self.file, 'seek'):
                        self.file.seek(0)
                    raw_bytes = self.file.read()
                    if hasattr(self.file, 'seek'):
                        self.file.seek(0)

                    # Compute SHA-256 digest of original plaintext content
                    if not self.file_hash:
                        self.file_hash = hashlib.sha256(raw_bytes).hexdigest()
                    if not self.file_size:
                        self.file_size = len(raw_bytes)

                    # Set key version from current settings
                    self.key_version = getattr(settings, 'VAULT_KEY_VERSION', 1)

                    # Encrypt plaintext bytes using AES-256-GCM with document UUID as AAD
                    aad = str(self.uuid).encode('utf-8')
                    encrypted_bytes = encrypt_bytes(raw_bytes, associated_data=aad)
                    self.file = ContentFile(encrypted_bytes, name=self.original_filename or self.file.name)
                    self.is_encrypted = True
                except Exception as e:
                    logger.error("Failed to encrypt document '%s' during save: %s", getattr(self, 'title', 'untitled'), e)
                    raise
            elif not self.file_hash:
                try:
                    self.file.open('rb')
                    data = self.file.read()
                    self.file_hash = hashlib.sha256(data).hexdigest()
                    self.file_size = len(data)
                except Exception:
                    pass
                finally:
                    self.file.close()

        super().save(*args, **kwargs)

    def get_decrypted_content(self) -> bytes:
        """
        Reads and returns decrypted document bytes from storage.
        If is_encrypted is True, verifies AES-256-GCM tag and decrypts payload using
        the document UUID as associated data (AAD) and the recorded key_version.
        If is_encrypted is False (legacy unencrypted file), returns raw bytes directly.
        """
        if not self.file:
            return b""

        self.file.open('rb')
        try:
            raw_bytes = self.file.read()
        finally:
            self.file.close()

        if self.is_encrypted:
            aad = str(self.uuid).encode('utf-8') if self.uuid else None
            return decrypt_bytes(
                raw_bytes,
                key_version=self.key_version,
                associated_data=aad,
                allow_legacy=True
            )
        return raw_bytes


    @property
    def formatted_size(self):
        """Human-readable file size string (e.g. 2.4 MB, 450 KB)."""
        if not self.file_size:
            return "0 KB"
        size = float(self.file_size)
        if size < 1024:
            return f"{size:.0f} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    @property
    def is_pdf(self):
        """Check if document is a PDF format safely."""
        if not self.file:
            return False
        file_type_pdf = bool(self.file_type and self.file_type.lower() == 'application/pdf')
        file_name_pdf = bool(getattr(self.file, 'name', None) and str(self.file.name).lower().endswith('.pdf'))
        return file_type_pdf or file_name_pdf

    @property
    def is_image(self):
        """Check if document is an image format safely."""
        if not self.file:
            return False
        file_type_img = bool(self.file_type and self.file_type.lower().startswith('image/'))
        file_name_img = bool(getattr(self.file, 'name', None) and str(self.file.name).lower().endswith(('.png', '.jpg', '.jpeg', '.webp')))
        return file_type_img or file_name_img

    @property
    def category_icon(self):
        """Material symbol icon for the domain."""
        icon_map = {
            'medical': 'medical_services',
            'education': 'school',
            'vehicle': 'directions_car',
            'personal': 'badge',
            'professional': 'work',
            'other': 'description',
        }
        return icon_map.get(self.category, 'description')

