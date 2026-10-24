"""
Django settings for Passli project.
Configured for local development, testing, and production deployment on Railway / Render.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

import warnings

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
DEFAULT_INSECURE_SECRET = 'django-insecure-_h5!zlxj*wxis-s=)i3a1^jqlwol@8@^%-m(bec8nznl0s4ybm'
SECRET_KEY = os.environ.get('SECRET_KEY', DEFAULT_INSECURE_SECRET)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

if not DEBUG and (SECRET_KEY == DEFAULT_INSECURE_SECRET or SECRET_KEY.startswith('django-insecure-')):
    if not any(cmd in sys.argv for cmd in ('test', 'pytest', 'makemigrations', 'migrate', 'collectstatic', 'check', 'ensure_superadmin')):
        raise ImproperlyConfigured("SECRET_KEY must be configured with a secure value in production when DEBUG=False.")

# Vault Master Encryption Key (AES-256-GCM 32-byte key, hex or base64)
VAULT_MASTER_KEY = os.environ.get('VAULT_MASTER_KEY')
VAULT_MASTER_KEY_PREVIOUS = os.environ.get('VAULT_MASTER_KEY_PREVIOUS')
VAULT_KEY_VERSION = int(os.environ.get('VAULT_KEY_VERSION', '1'))

# In automated test runs without explicit key, provide a deterministic 32-byte test key
if any(cmd in sys.argv for cmd in ('test', 'pytest')) and not VAULT_MASTER_KEY:
    VAULT_MASTER_KEY = '0' * 64

# Allowed Hosts configuration (comma-separated env var)
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]

# CSRF Trusted Origins (required for POST forms on HTTPS domains, comma-separated env var)
csrf_origins_env = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000'
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_env.split(',') if o.strip()]

# Reverse proxy SSL header & trusted proxy configuration
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
raw_proxy_count = os.environ.get('TRUSTED_PROXY_COUNT')
if not DEBUG and raw_proxy_count is None and not any(cmd in sys.argv for cmd in ('test', 'pytest', 'makemigrations', 'migrate', 'collectstatic', 'check', 'ensure_superadmin')):
    warnings.warn(
        "TRUSTED_PROXY_COUNT environment variable is not explicitly set. Defaulting to 1. "
        "Verify reverse proxy depth for client IP extraction in audit logs.",
        UserWarning,
        stacklevel=2,
    )
TRUSTED_PROXY_COUNT = int(raw_proxy_count) if raw_proxy_count and raw_proxy_count.isdigit() else 1

# Defense-in-Depth HTTP Security Headers & Cookie Policies
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400  # 24-hour expiration
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
if any(cmd in sys.argv for cmd in ('test', 'pytest')):
    SECURE_SSL_REDIRECT = False
    from django.contrib.auth.hashers import PBKDF2PasswordHasher

    class FastPBKDF2PasswordHasher(PBKDF2PasswordHasher):
        iterations = 1

    PASSWORD_HASHERS = [
        'config.settings.FastPBKDF2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
else:
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True' if not DEBUG else 'False').lower() in ('true', '1', 't')

if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Passli Core Apps
    'accounts.apps.AccountsConfig',
    'documents.apps.DocumentsConfig',
    'sharing.apps.SharingConfig',
    'audit.apps.AuditConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'config.context_processors.email_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database Configuration
# Uses PostgreSQL if DATABASE_URL is set, falls back to SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    db_path_env = os.environ.get('DATABASE_PATH')
    sqlite_path = Path(db_path_env).resolve() if db_path_env else BASE_DIR / 'db.sqlite3'
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
            'OPTIONS': {
                'timeout': 60,
            },
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# WhiteNoise enables direct, production-grade static file serving
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media files (Uploaded User Documents & Vault Files)
MEDIA_URL = '/media/'
raw_media_root = os.environ.get('MEDIA_ROOT')
MEDIA_ROOT = Path(raw_media_root).resolve() if raw_media_root else BASE_DIR / 'media'

try:
    os.makedirs(MEDIA_ROOT, exist_ok=True)
    os.makedirs(MEDIA_ROOT / 'vault_files', exist_ok=True)
except OSError as e:
    import logging
    logging.getLogger('config').warning("Failed to create media directory at %s: %s", MEDIA_ROOT, e)

# File upload limits (5 MB limit)
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# Authentication redirects
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'landing'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Production Logging Configuration (Captures all 500 errors and app logs in Railway console)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{asctime}] {levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'documents': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'sharing': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'audit': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# ==============================================================================
# Email & SMTP Service Configuration (Gmail SMTP & Standard Providers)
# ==============================================================================
raw_host = os.environ.get('SMTP_HOST', os.environ.get('EMAIL_HOST', 'smtp.gmail.com'))
EMAIL_HOST = raw_host.strip().strip("'\"") if raw_host else 'smtp.gmail.com'

# Change default SMTP_PORT to 587 with STARTTLS (keep 465 SSL when explicitly set)
raw_port = str(os.environ.get('SMTP_PORT', os.environ.get('EMAIL_PORT', '587'))).strip().strip("'\"")
EMAIL_PORT = int(raw_port) if raw_port.isdigit() else 587

if EMAIL_PORT == 465:
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
else:
    EMAIL_USE_SSL = False
    EMAIL_USE_TLS = True

raw_user = os.environ.get('SMTP_USER', os.environ.get('EMAIL_HOST_USER', ''))
EMAIL_HOST_USER = raw_user.strip().strip("'\"") if raw_user else ''

# Clean Google App Password: strip quotes, trim whitespace, and REMOVE SPACES
raw_pass = os.environ.get('SMTP_PASS', os.environ.get('EMAIL_HOST_PASSWORD', ''))
EMAIL_HOST_PASSWORD = raw_pass.strip().strip("'\"").replace(' ', '') if raw_pass else ''

raw_from = os.environ.get('EMAIL_FROM', os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@passli.dev'))
DEFAULT_FROM_EMAIL = raw_from.strip().strip("'\"") if raw_from else (EMAIL_HOST_USER or 'noreply@passli.dev')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 12  # 12-second timeout

if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    EMAIL_SERVICE_CONFIGURED = False
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    if not any(cmd in sys.argv for cmd in ('test', 'pytest', 'makemigrations', 'migrate', 'collectstatic', 'check', 'ensure_superadmin')):
        import logging
        logging.getLogger('config').warning(
            "SMTP_USER or SMTP_PASS is empty. Outbound email is disabled; using console EmailBackend. "
            "Registration verification codes and alerts will be printed to console."
        )
else:
    EMAIL_SERVICE_CONFIGURED = True
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')


# ==============================================================================
# Public Application Base URL (for generating trusted reset, verification, and alert links)
# ==============================================================================
def validate_app_url(debug: bool, url: str) -> None:
    """Validate that APP_URL is configured with an HTTPS URL in production."""
    if not debug and (not url or url.startswith(('http://localhost', 'http://127.0.0.1'))):
        raise ImproperlyConfigured(
            "APP_URL must be configured with a valid public HTTPS origin in production (DEBUG=False), "
            "e.g. 'https://<username>.pythonanywhere.com'."
        )


raw_app_url = os.environ.get('APP_URL', '').strip().strip("'\"").rstrip('/')
if not any(cmd in sys.argv for cmd in ('test', 'pytest', 'makemigrations', 'migrate', 'collectstatic', 'check', 'ensure_superadmin')):
    validate_app_url(DEBUG, raw_app_url)

APP_URL = raw_app_url if raw_app_url else 'http://localhost:8000'

