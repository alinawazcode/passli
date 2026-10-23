import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.urls import reverse


class SharePass(models.Model):
    """
    Represents a time-gated, cryptographic Share Pass for one or more vault documents.
    Plaintext share keys are NEVER stored in the database; only salted PBKDF2 hashes are retained.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='share_passes'
    )
    documents = models.ManyToManyField(
        'documents.Document',
        related_name='share_passes',
        blank=False
    )
    title = models.CharField(max_length=120, blank=True, help_text="Optional description or purpose of this Share Pass")
    key_hash = models.CharField(max_length=255, help_text="PBKDF2 cryptographic hash of the raw 8-character Share Key")
    can_view = models.BooleanField(default=True, help_text="Permits in-browser decrypted viewing of shared documents")
    can_download = models.BooleanField(default=False, help_text="Permits downloading raw decrypted files to recipient machine")
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text="Strict expiration timestamp after which access is denied")
    is_revoked = models.BooleanField(default=False, db_index=True, help_text="Immediate owner revocation flag")
    access_count = models.PositiveIntegerField(default=0, help_text="Number of successful accesses by recipients")
    max_uses = models.PositiveIntegerField(default=0, help_text="Maximum allowed accesses before pass expires (0 = unlimited during TTL)")
    global_failed_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Total failed key attempts across all IP addresses for rate limiting"
    )
    global_window_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start timestamp of current global failure rate window"
    )
    global_locked_until = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp until which pass is globally locked across all IPs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Share Pass'
        verbose_name_plural = 'Share Passes'

    def __str__(self):
        label = self.title or f"Share Pass {str(self.id)[:8]}"
        return f"{label} ({self.owner.username})"

    def set_key(self, raw_key: str):
        """Hashes and stores the raw Share Key."""
        self.key_hash = make_password(raw_key.strip().upper())

    def verify_key(self, raw_key: str) -> bool:
        """Verifies a submitted raw key against the stored PBKDF2 hash."""
        if not raw_key or not self.key_hash:
            return False
        # Normalize key: uppercase and strip whitespace/hyphens if entered without hyphen
        cleaned_key = raw_key.strip().upper()
        # Direct check with hyphen
        if check_password(cleaned_key, self.key_hash):
            return True
        # If user entered without hyphen (e.g. 8K7P42XM), also test formatted version
        if len(cleaned_key) == 8 and '-' not in cleaned_key:
            formatted = f"{cleaned_key[:4]}-{cleaned_key[4:]}"
            if check_password(formatted, self.key_hash):
                return True
        return False

    check_key = verify_key

    def is_limit_reached(self) -> bool:
        """Checks if single-use or limited use pass has met max uses limit."""
        return bool(self.max_uses > 0 and self.access_count >= self.max_uses)

    def is_expired(self) -> bool:
        """Checks if the pass has surpassed its expiration timestamp or max usage."""
        if self.expires_at and timezone.now() >= self.expires_at:
            return True
        if self.is_limit_reached():
            return True
        return False

    def is_active(self) -> bool:
        """A pass is active only if it is NOT revoked and NOT expired."""
        return not self.is_revoked and not self.is_expired()

    @property
    def is_globally_locked(self) -> bool:
        """Checks if pass is currently locked across all IPs due to global failure limit."""
        if self.global_locked_until and self.global_locked_until > timezone.now():
            return True
        return False

    @property
    def global_retry_after_seconds(self) -> int:
        """Returns seconds remaining for global lockout, minimum 1 second."""
        if not self.global_locked_until:
            return 0
        diff = (self.global_locked_until - timezone.now()).total_seconds()
        return max(1, int(diff + 0.999))

    def revoke(self):
        """Immediately revokes access to this Share Pass."""
        self.is_revoked = True
        self.save(update_fields=['is_revoked', 'updated_at'])

    @property
    def status_label(self) -> str:
        """Returns human-readable status badge label."""
        if self.is_revoked:
            return "Revoked"
        if self.is_expired():
            return "Expired"
        return "Active"

    @property
    def time_remaining_seconds(self) -> int:
        """Returns seconds remaining before expiration, or 0 if expired."""
        if self.is_expired() or not self.expires_at:
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, int(delta.total_seconds()))

    def get_absolute_url(self):
        return reverse('share_detail', kwargs={'pass_id': self.id})

    def get_recipient_url(self, request=None) -> str:
        """Returns public recipient URL for QR code and sharing."""
        path = reverse('recipient_verify', kwargs={'pass_id': self.id})
        if request:
            return request.build_absolute_uri(path)
        return path


class SharePassLockout(models.Model):
    """
    Persistent database-backed rate-limiting lockout tracker for SharePass access.
    Tracks failed verification attempts per pass and per IP address with exponential backoff.
    """
    share_pass = models.ForeignKey(
        'sharing.SharePass',
        on_delete=models.CASCADE,
        related_name='lockouts',
        db_index=True
    )
    ip_address = models.CharField(max_length=45, db_index=True, default='127.0.0.1')
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['share_pass', 'ip_address'], name='unique_share_pass_ip_lockout')
        ]
        indexes = [
            models.Index(fields=['share_pass', 'ip_address']),
            models.Index(fields=['locked_until']),
        ]
        verbose_name = 'Share Pass Lockout'
        verbose_name_plural = 'Share Pass Lockouts'

    def __str__(self):
        return f"Lockout for {self.share_pass_id} from {self.ip_address} ({self.failed_attempts} fails)"

    @property
    def is_locked(self) -> bool:
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    @property
    def retry_after_seconds(self) -> int:
        if not self.locked_until:
            return 0
        diff = (self.locked_until - timezone.now()).total_seconds()
        return max(1, int(diff + 0.999))


