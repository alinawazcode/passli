# Passli Production Deployment & Operations Guide

This guide covers deployment workflows for Passli across PythonAnywhere, Docker, Render, VPS/Nginx, and PaaS infrastructures.

---

## 1. Deployment Architecture & Prerequisites

Passli can run on any WSGI/ASGI-compatible Python 3.12 hosting environment, including PythonAnywhere, Render, Fly.io, Docker containers, and Linux VPS servers (with Nginx + Gunicorn).

### 1.1 Key Deployment Considerations
1. **Persistent Media Storage**:
   - Encrypted vault documents are saved to disk under `media/vault_files/` (or the directory pointed to by `MEDIA_ROOT`).
   - On hosts with ephemeral storage (e.g. Render, Fly.io), attach a **Persistent Volume** mounted at `/app/media`. On PythonAnywhere and VPS hosts, storage is persistent by default.
2. **Master Encryption Key**:
   - `VAULT_MASTER_KEY` is strictly required in production (`DEBUG=False`).
   - Loss of this key permanently destroys all encrypted documents in the vault. Back it up securely off-host.
3. **Database Migration & Initialization**:
   - Apply migrations:
     ```bash
     python manage.py migrate
     ```
   - Collect static assets:
     ```bash
     python manage.py collectstatic --noinput
     ```
   - One-off superadmin provisioning (optional):
     ```bash
     python manage.py ensure_superadmin
     ```

---

## 2. Production Environment Variables Checklist

| Variable | Description | Required | Example |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | Django cryptographic signing secret | Yes | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | Application debug mode | Yes | `False` |
| `VAULT_MASTER_KEY` | 32-byte hex master key for AES-256-GCM | Yes | Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `VAULT_MASTER_KEY_PREVIOUS` | Previous master key (for key rotation) | Optional | 32-byte hex string |
| `VAULT_KEY_VERSION` | Current key version identifier | Optional | `1` |
| `ALLOWED_HOSTS` | Comma-separated allowed host headers | Yes | `localhost,127.0.0.1,yourusername.pythonanywhere.com` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origin URLs | Yes | `https://yourusername.pythonanywhere.com` |
| `APP_URL` | Public HTTPS URL for generating email links | Yes | `https://yourusername.pythonanywhere.com` |
| `DATABASE_URL` | PostgreSQL or external DB connection string | Optional | `postgresql://user:pass@host:5432/db` (defaults to SQLite) |
| `TRUSTED_PROXY_COUNT` | Number of trusted upstream reverse proxies | Yes | `1` |
| `DJANGO_SUPERUSER_USERNAME` | Superadmin initial username | Optional | `admin` |
| `DJANGO_SUPERUSER_PASSWORD` | Superadmin initial password | Optional | Strong random password |
| `DJANGO_SUPERUSER_EMAIL` | Superadmin initial email | Optional | `admin@passli.dev` |
| `SMTP_HOST` | Transactional email SMTP server | Yes | `smtp.gmail.com` |
| `SMTP_PORT` | Transactional email port (465=SSL, 587=TLS) | Yes | `587` |
| `SMTP_USER` | Email account username | Yes | `your-email@gmail.com` |
| `SMTP_PASS` | 16-character Google App Password (no spaces) | Yes | `abcdefghijklmnop` |
| `EMAIL_FROM` | Sender display email | Yes | `your-email@gmail.com` |

---

## 3. Docker Deployment

### 3.1 Dockerfile Architecture
The project root contains a hardened `Dockerfile` with:
- Minimal `python:3.12-slim` base image.
- Dedicated unprivileged system user (`appuser`, UID 1000).
- Healthcheck hitting the landing page via dynamic `PORT`.
- Non-root filesystem permissions for `staticfiles`, `media`, and `vault_storage`.

### 3.2 Build & Run
```bash
# Build production image
docker build -t passli:latest .

# Run container with environment configuration
docker run -d \
  -p 8000:8000 \
  -v passli_media:/app/media \
  -e SECRET_KEY="your-production-secret-key" \
  -e VAULT_MASTER_KEY="your-32-byte-hex-master-key" \
  -e DEBUG="False" \
  -e ALLOWED_HOSTS="localhost,127.0.0.1" \
  --name passli_app \
  passli:latest
```

---

## 4. Operational Maintenance & Runbook

### 4.1 Encrypting Legacy Files / Key Rotation
```bash
# Preview unencrypted files without altering data
python manage.py encrypt_vault_storage --dry-run

# Execute live encryption
python manage.py encrypt_vault_storage --batch-size 100

# Re-encrypt legacy files with UUID AAD and new key version after rotating keys
python manage.py encrypt_vault_storage --reencrypt-legacy
```

### 4.2 SMTP Health Check
```bash
# Test SMTP authentication, TLS handshake, and dispatch
python manage.py test_smtp admin@passli.dev
```

### 4.3 Superadmin Provisioning
```bash
# Idempotently ensure superadmin exists from environment variables without resetting existing passwords
python manage.py ensure_superadmin
```

### 4.4 Verifying TRUSTED_PROXY_COUNT & Client IP Extraction
Passli uses reverse proxy headers (`X-Forwarded-For`) to record true client IP addresses for lockout tracking and security audit logs.
To verify that upstream proxy depth is configured correctly and immune to client IP spoofing:

1. Send a test request containing a forged `X-Forwarded-For` header:
   ```bash
   curl -H "X-Forwarded-For: 203.0.113.199" https://<your-domain>/accounts/login/
   ```
2. Inspect the audit log in the administrative dashboard (`/admin/dashboard/audit/`) or application console:
   - **Correctly configured (`TRUSTED_PROXY_COUNT=1`)**: The audit log records your actual public IP address; the spoofed `203.0.113.199` is ignored.
   - **Misconfigured (proxy count set too high)**: The audit log records `203.0.113.199`. In this case, lower `TRUSTED_PROXY_COUNT` until only authentic upstream proxies are trusted.
