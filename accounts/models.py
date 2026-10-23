import hashlib
import secrets
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class UserProfile(models.Model):
    """
    Extends standard auth.User with verification status and security profile details.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    is_email_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether the user has verified ownership of their email address."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Security Profile"
        verbose_name_plural = "User Security Profiles"

    def __str__(self):
        status = "Verified" if self.is_email_verified else "Unverified"
        return f"{self.user.username} ({status})"


class EmailVerificationCode(models.Model):
    """
    Time-limited, single-use 6-digit numeric OTP code for verifying email addresses.
    Plaintext codes are never stored; only salted PBKDF2 hashes are persisted.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_codes',
        db_index=True
    )
    email = models.EmailField(
        help_text="Target email address being verified."
    )
    code_hash = models.CharField(
        max_length=255,
        help_text="PBKDF2 hash of the 6-digit OTP code."
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed verification attempts."
    )
    max_attempts = models.PositiveIntegerField(
        default=5,
        help_text="Max permitted incorrect submissions before code invalidation."
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Expiration timestamp (defaults to 15 minutes after generation)."
    )
    is_used = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag indicating whether this OTP was already successfully verified."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Email Verification Code"
        verbose_name_plural = "Email Verification Codes"

    def __str__(self):
        return f"OTP for {self.email} ({'used' if self.is_used else 'active'})"

    def set_code(self, raw_code: str):
        """Hashes and sets the 6-digit OTP code."""
        self.code_hash = make_password(str(raw_code).strip())

    def verify_code(self, submitted_code: str) -> bool:
        """
        Validates the submitted OTP against hash, enforcing expiration, attempt limits,
        and single-use status.
        """
        if self.is_used:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.attempts >= self.max_attempts:
            return False

        self.attempts += 1
        is_correct = check_password(str(submitted_code).strip(), self.code_hash)
        if is_correct:
            self.is_used = True
            self.save(update_fields=['attempts', 'is_used'])
            return True
        else:
            self.save(update_fields=['attempts'])
            return False

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_locked(self) -> bool:
        return self.attempts >= self.max_attempts


class PasswordResetToken(models.Model):
    """
    Cryptographically secure, unpredictable, single-use password reset tokens.
    Only SHA-256 token hashes are stored to protect tokens at rest.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
        db_index=True
    )
    token_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 digest of the raw URL-safe reset token."
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Token expiration timestamp (defaults to 30 minutes)."
    )
    is_used = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Single-use flag ensuring tokens cannot be replayed."
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Requesting client IP address."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"

    def __str__(self):
        return f"ResetToken for {self.user.username} ({'used' if self.is_used else 'valid'})"

    @classmethod
    def create_token_for_user(cls, user, ip_address: str = None, ttl_minutes: int = 30) -> tuple:
        """
        Generates a new unpredictable 32-byte URL-safe token, hashes it,
        and saves the record. Returns (instance, raw_token).
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        expires_at = timezone.now() + timedelta(minutes=ttl_minutes)

        # Invalidate any existing unused tokens for this user
        cls.objects.filter(user=user, is_used=False).update(is_used=True)

        record = cls.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
        )
        return record, raw_token

    @classmethod
    def get_valid_token(cls, raw_token: str):
        """
        Validates raw token against stored SHA-256 hash. Returns record or None.
        """
        if not raw_token:
            return None
        token_hash = hashlib.sha256(raw_token.strip().encode('utf-8')).hexdigest()
        try:
            record = cls.objects.get(
                token_hash=token_hash,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            return record
        except cls.DoesNotExist:
            return None

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])


class SecurityAlertLog(models.Model):
    """
    Maintains rate-limiting, cooldown, and aggregation state for outgoing security emails
    (e.g., failed QR/passcode verification alerts) to prevent inbox flooding.
    """
    alert_type = models.CharField(
        max_length=60,
        db_index=True,
        help_text="Type of security alert (e.g., failed_passcode, suspicious_login)."
    )
    identifier = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Entity key, e.g. pass:<uuid> or user:<id>."
    )
    recipient_email = models.EmailField()
    attempts_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of aggregated failed attempts since last alert."
    )
    last_alert_at = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when the last email alert was dispatched."
    )
    last_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_alert_at']
        unique_together = ('alert_type', 'identifier')
        verbose_name = "Security Alert Cooldown Log"
        verbose_name_plural = "Security Alert Cooldown Logs"

    def __str__(self):
        return f"{self.alert_type} for {self.identifier} ({self.attempts_count} attempts)"

    @classmethod
    def check_and_record_alert(
        cls,
        alert_type: str,
        identifier: str,
        recipient_email: str,
        ip_address: str = None,
        cooldown_seconds: int = 900
    ) -> tuple[bool, int]:
        """
        Records an attempt. Returns (should_send_email: bool, total_attempts_in_window: int).
        If within cooldown period, suppresses email dispatch and accumulates attempts_count.
        If cooldown period has elapsed, updates last_alert_at and returns should_send_email=True.
        """
        # Validate ip_address for GenericIPAddressField (PostgreSQL inet compatibility)
        clean_ip = None
        if ip_address:
            import ipaddress
            try:
                ipaddress.ip_address(ip_address)
                clean_ip = ip_address
            except (ValueError, TypeError):
                clean_ip = None

        now = timezone.now()
        record, created = cls.objects.get_or_create(
            alert_type=alert_type,
            identifier=identifier,
            defaults={
                'recipient_email': recipient_email,
                'attempts_count': 1,
                'last_alert_at': now,
                'last_ip': clean_ip,
            }
        )

        if created:
            return True, 1

        delta = (now - record.last_alert_at).total_seconds()
        record.last_ip = clean_ip
        record.recipient_email = recipient_email

        if delta >= cooldown_seconds:
            # Cooldown passed; send a new aggregated email
            total = record.attempts_count + 1
            record.attempts_count = 1
            record.last_alert_at = now
            record.save(update_fields=['attempts_count', 'last_alert_at', 'last_ip', 'recipient_email'])
            return True, total
        else:
            # Within cooldown; suppress duplicate email but record failure count
            record.attempts_count += 1
            record.save(update_fields=['attempts_count', 'last_ip', 'recipient_email'])
            return False, record.attempts_count
