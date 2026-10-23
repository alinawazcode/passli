from django.db import models
from django.conf import settings


class ShareAccessLog(models.Model):
    """
    Immutable structured audit trail recording all access attempts, document views,
    download streams, verification failures, rate limit lockouts, and owner revocations.
    """
    class EventType(models.TextChoices):
        KEY_SUCCESS = 'key_success', 'Key Verified'
        KEY_FAILED = 'key_failed', 'Invalid Key Attempt'
        RATE_LOCKED = 'rate_locked', 'Brute-Force Lockout'
        VIEW_PORTAL = 'view_portal', 'Portal Session Opened'
        VIEW_DOC = 'view_doc', 'Document Previewed'
        DOWNLOAD_DOC = 'download_doc', 'Document Downloaded'
        SESSION_LEFT = 'session_left', 'Session Closed'
        PASS_REVOKED = 'pass_revoked', 'Pass Revoked by Owner'
        PASS_EXPIRED = 'pass_expired', 'Expired Access Attempt'

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        DENIED = 'denied', 'Denied'
        LOCKED = 'locked', 'Locked'
        EXPIRED = 'expired', 'Expired'
        REVOKED = 'revoked', 'Revoked'

    share_pass = models.ForeignKey(
        'sharing.SharePass',
        on_delete=models.CASCADE,
        related_name='access_logs',
        db_index=True
    )
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_logs'
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUCCESS,
        db_index=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    details = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Share Access Log'
        verbose_name_plural = 'Share Access Logs'
        indexes = [
            models.Index(fields=['share_pass', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
        ]

    def __str__(self):
        pass_name = self.share_pass.title if (self.share_pass and self.share_pass.title) else f"Pass #{str(self.share_pass.id)[:8]}"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.get_event_type_display()} — {pass_name} ({self.status})"

    @property
    def event_icon(self) -> str:
        """Returns material icon string representing this event."""
        icons = {
            self.EventType.KEY_SUCCESS: 'key',
            self.EventType.KEY_FAILED: 'key_off',
            self.EventType.RATE_LOCKED: 'lock',
            self.EventType.VIEW_PORTAL: 'dashboard',
            self.EventType.VIEW_DOC: 'visibility',
            self.EventType.DOWNLOAD_DOC: 'download',
            self.EventType.SESSION_LEFT: 'logout',
            self.EventType.PASS_REVOKED: 'block',
            self.EventType.PASS_EXPIRED: 'timer_off',
        }
        return icons.get(self.event_type, 'info')


def get_client_ip(request) -> str | None:
    """
    Extracts client IP address from request, checking forwarded headers using
    TRUSTED_PROXY_COUNT to guard against spoofed X-Forwarded-For headers.
    Takes the entry TRUSTED_PROXY_COUNT hops from the right.
    If the header has fewer entries than expected, falls back to REMOTE_ADDR.
    Never trusts the leftmost entry.
    """
    if not request:
        return None

    remote_addr = request.META.get('REMOTE_ADDR')
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        trusted_proxies = getattr(settings, 'TRUSTED_PROXY_COUNT', 1)
        ips = [ip.strip() for ip in x_forwarded_for.split(',') if ip.strip()]
        if trusted_proxies > 0 and len(ips) >= trusted_proxies:
            return ips[-trusted_proxies]
        return remote_addr

    return remote_addr


def log_share_event(
    share_pass,
    event_type: str,
    request=None,
    document=None,
    status: str = ShareAccessLog.Status.SUCCESS,
    details: str = ''
) -> ShareAccessLog:
    """
    Helper function to record a structured audit event in the database.
    """
    ip = get_client_ip(request) if request else None
    user_agent = ''
    if request:
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    return ShareAccessLog.objects.create(
        share_pass=share_pass,
        document=document,
        event_type=event_type,
        status=status,
        ip_address=ip,
        user_agent=user_agent,
        details=details[:255] if details else ''
    )
