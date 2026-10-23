"""
Django settings for Passli project.
Configured for local development, testing, and production deployment on Railway / Render.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

from django.core.exceptions import ImproperlyConfigured

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
DEFAULT_INSECURE_SECRET = 'django-insecure-_h5!zlxj*wxis-s=)i3a1^jqlwol@8@^%-m(bec8nznl0s4ybm'
SECRET_KEY = os.environ.get('SECRET_KEY', DEFAULT_INSECURE_SECRET)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

if not DEBUG and (SECRET_KEY == DEFAULT_INSECURE_SECRET or SECRET_KEY.startswith('django-insecure-')):
    if not any(cmd in sys.argv for cmd in ('test', 'pytest', 'makemigrations', 'migrate')):
        raise ImproperlyConfigured("SECRET_KEY must be configured with a secure value in production when DEBUG=False.")

# Vault Master Encryption Key (AES-256-GCM 32-byte key, hex or base64)
VAULT_MASTER_KEY = os.environ.get('VAULT_MASTER_KEY')
VAULT_MASTER_KEY_PREVIOUS = os.environ.get('VAULT_MASTER_KEY_PREVIOUS')
VAULT_KEY_VERSION = int(os.environ.get('VAULT_KEY_VERSION', '1'))

# In automated test runs without explicit key, provide a deterministic 32-byte test key
if any(cmd in sys.argv for cmd in ('test', 'pytest')) and not VAULT_MASTER_KEY:
    VAULT_MASTER_KEY = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'

# Allowed Hosts configuration
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]

# Add Railway public domain dynamically if present
railway_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if railway_domain and railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(railway_domain)

# CSRF Trusted Origins (required for POST forms on HTTPS domains)
csrf_origins_env = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000'
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_env.split(',') if o.strip()]
if railway_domain:
    railway_origin = f"https://{railway_domain}"
    if railway_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(railway_origin)

# Reverse proxy SSL header (Railway / Render / Nginx termination)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
TRUSTED_PROXY_COUNT = int(os.environ.get('TRUSTED_PROXY_COUNT', '1'))

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database Configuration
# Uses PostgreSQL if DATABASE_URL is set (Railway Postgres), falls back to SQLite
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
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
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
MEDIA_ROOT = BASE_DIR / 'media'
os.makedirs(MEDIA_ROOT, exist_ok=True)
os.makedirs(MEDIA_ROOT / 'vault_files', exist_ok=True)

# File upload limits (30 MB limit)
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024

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
# Email & SMTP Service Configuration (Gmail SMTP & Railway Environment Compatible)
# ==============================================================================
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')

raw_host = os.environ.get('SMTP_HOST', os.environ.get('EMAIL_HOST', 'smtp.gmail.com'))
EMAIL_HOST = raw_host.strip().strip("'\"") if raw_host else 'smtp.gmail.com'

raw_port = str(os.environ.get('SMTP_PORT', os.environ.get('EMAIL_PORT', '465'))).strip().strip("'\"")
EMAIL_PORT = int(raw_port) if raw_port.isdigit() else 465

# SMTP Security: port 465 uses SSL directly (EMAIL_USE_SSL = True); port 587 uses STARTTLS (EMAIL_USE_TLS = True)
smtp_secure_env = str(os.environ.get('SMTP_SECURE', 'true')).strip().strip("'\"").lower() in ('true', '1', 't', 'yes')
if EMAIL_PORT == 465:
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False
elif EMAIL_PORT == 587 or not smtp_secure_env:
    EMAIL_USE_SSL = False
    EMAIL_USE_TLS = True
else:
    EMAIL_USE_SSL = True
    EMAIL_USE_TLS = False

raw_user = os.environ.get('SMTP_USER', os.environ.get('EMAIL_HOST_USER', ''))
EMAIL_HOST_USER = raw_user.strip().strip("'\"") if raw_user else ''

# Clean Google App Password: strip quotes, trim whitespace, and REMOVE SPACES
# (Google generates app passwords formatted like 'abcd efgh ijkl mnop' which fail if spaces aren't stripped)
raw_pass = os.environ.get('SMTP_PASS', os.environ.get('EMAIL_HOST_PASSWORD', ''))
EMAIL_HOST_PASSWORD = raw_pass.strip().strip("'\"").replace(' ', '') if raw_pass else ''

raw_from = os.environ.get('EMAIL_FROM', os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@passli.dev'))
DEFAULT_FROM_EMAIL = raw_from.strip().strip("'\"") if raw_from else (EMAIL_HOST_USER or 'noreply@passli.dev')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 12  # 12-second timeout

# Public Application Base URL (for generating trusted reset, verification, and alert links)
raw_app_url = os.environ.get('APP_URL', '').strip().strip("'\"").rstrip('/')
if not raw_app_url and railway_domain:
    raw_app_url = f"https://{railway_domain}"
if not raw_app_url:
    raw_app_url = 'http://localhost:8000'
APP_URL = raw_app_url

