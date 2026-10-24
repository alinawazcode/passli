from django.conf import settings


def email_status(request):
    """Exposes email delivery service configuration status to templates."""
    return {
        'email_service_configured': getattr(settings, 'EMAIL_SERVICE_CONFIGURED', True),
    }
