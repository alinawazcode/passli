# Passli Production Deployment & Operations Guide

This guide covers deployment workflows for Passli across Railway, Docker, Render, and custom VPS/Nginx infrastructures.

---

## 1. Railway Deployment (Primary PaaS Target)

Passli is optimized for deployment on [Railway](https://railway.com/) with native support for `railway.json` and `nixpacks.toml`.

### 1.1 Deployment Steps
1. Create a new project in Railway from your GitHub repository.
2. Add a **PostgreSQL** database service (Railway automatically populates `DATABASE_URL`).
3. In the Web service, attach a **Persistent Volume**:
   - Mount Path: `/app/media`
   - *Why*: Encrypted vault documents are saved to disk under `media/vault_files/`. Without a persistent volume, container restarts and redeployments will wipe uploaded documents.
4. Add required environment variables under the **Variables** tab (see Section 2).
5. Trigger deployment. Nixpacks builds the dependencies and starts Gunicorn with:
   ```bash
   python manage.py migrate && python manage.py ensure_superadmin && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
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
| `ALLOWED_HOSTS` | Comma-separated allowed host headers | Yes | `localhost,127.0.0.1,web-production-xxxx.up.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origin URLs | Yes | `https://web-production-xxxx.up.railway.app` |
| `APP_URL` | Public HTTPS URL for generating email links | Yes | `https://web-production-xxxx.up.railway.app` |
| `DATABASE_URL` | PostgreSQL connection string | Yes | `postgresql://user:pass@host:5432/db` |
| `TRUSTED_PROXY_COUNT` | Number of trusted upstream reverse proxies | Yes | `1` |
| `DJANGO_SUPERUSER_USERNAME` | Superadmin initial username | Recommended | `admin` |
| `DJANGO_SUPERUSER_PASSWORD` | Superadmin initial password | Recommended | Strong random password |
| `DJANGO_SUPERUSER_EMAIL` | Superadmin initial email | Recommended | `admin@passli.dev` |
| `SMTP_HOST` | Transactional email SMTP server | Yes | `smtp.gmail.com` |
| `SMTP_PORT` | Transactional email port (465=SSL, 587=TLS) | Yes | `465` |
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
