# Deploying Passli on PythonAnywhere (Free Tier)

This guide walks through deploying Passli on the **PythonAnywhere Free (Beginner)** plan from scratch using Python 3.12, SQLite, and Gmail SMTP.

---

## 1. Create a Free PythonAnywhere Account
1. Sign up for a free Beginner account at [pythonanywhere.com](https://www.pythonanywhere.com/).
2. Choose your username carefully: your public URL will be `https://<username>.pythonanywhere.com`.
3. In this guide, replace `<username>` with your actual PythonAnywhere username.

---

## 2. Clone Repository & Set Up Virtual Environment

1. From the PythonAnywhere dashboard, open a **Bash** console.
2. Clone the repository into your home directory:
   ```bash
   git clone https://github.com/alinawazcode/passli.git
   ```
3. Create and activate a dedicated Python 3.12 virtualenv using `virtualenvwrapper`:
   ```bash
   mkvirtualenv passli --python=python3.12
   ```
4. Navigate to the project directory and install application dependencies:
   ```bash
   cd ~/passli
   pip install -r requirements.txt
   ```

---

## 3. Configure Secrets & Environment Variables (`~/.env`)

To protect secrets against accidental commits and directory exposure, place your environment file at `~/.env` (in `/home/<username>/.env`), completely outside the Git repository.

### 3.1 Cryptographic Key & Secret Generation
Run these commands in your Bash console to generate production-grade cryptographically random strings:
```bash
# Generate Django SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"

# Generate 32-byte hex VAULT_MASTER_KEY for AES-256-GCM
python -c "import secrets; print('VAULT_MASTER_KEY=' + secrets.token_hex(32))"
```

> [!CAUTION]
> **CRITICAL: VAULT MASTER KEY BACKUP**
> `VAULT_MASTER_KEY` is the root key used to encrypt all files in your vault. If this key is lost, modified, or overwritten, **every document in your vault is permanently and irreversibly destroyed**. PythonAnywhere staff and Passli developers cannot decrypt or restore your documents without it. Save this key in a secure offline password manager immediately.

### 3.2 Create `/home/<username>/.env`
Create or edit the file with `nano ~/.env` and populate every variable below:

```bash
# Security & Debugging
SECRET_KEY=<generated-django-secret-key>
VAULT_MASTER_KEY=<generated-32-byte-hex-key>
DEBUG=False

# Host & Origin Whitelisting
ALLOWED_HOSTS=<username>.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://<username>.pythonanywhere.com
APP_URL=https://<username>.pythonanywhere.com
TRUSTED_PROXY_COUNT=1

# Email Service (Gmail SMTP via port 587 STARTTLS)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-dedicated-email@gmail.com
SMTP_PASS=your-16-char-google-app-password
EMAIL_FROM=your-dedicated-email@gmail.com

# Initial Superadmin Configuration (for ensure_superadmin command)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=your-secure-admin-password
DJANGO_SUPERUSER_EMAIL=admin@yourdomain.com
```

---

## 4. Database Migrations, Assets & Initial Superadmin

Run the following initialization commands in your Bash console:

```bash
cd ~/passli
set -a; source ~/.env; set +a

# 1. Apply database migrations
python manage.py migrate

# 2. Compile static assets into staticfiles/
python manage.py collectstatic --noinput

# 3. Create initial superadministrator account (one-off provisioning)
python manage.py ensure_superadmin

# 4. Verify SMTP email dispatch
python manage.py test_smtp your-personal-email@domain.com
```

Confirm that the SMTP test command reports successful TLS handshake and dispatches a test email.

---

## 5. Web Tab Configuration

Navigate to the **Web** tab in your PythonAnywhere dashboard:

1. Click **Add a new web app**.
2. Select **Manual configuration** (do NOT choose Django auto-configure, as we will use our existing virtual environment).
3. Select **Python 3.12**.
4. Configure the paths:
   - **Source code**: `/home/<username>/passli`
   - **Working directory**: `/home/<username>/passli`
   - **Virtualenv**: `/home/<username>/.virtualenvs/passli`
5. Configure **Static Files** mapping:
   - **URL**: `/static/`
   - **Directory**: `/home/<username>/passli/staticfiles`

> [!IMPORTANT]
> **NO MEDIA MAPPING**
> Do NOT create a static mapping for `/media/`. Encrypted files in Passli must never be served directly by the web server. Passli routes file downloads through authenticated owner views and time-gated recipient access views with AES-256-GCM verification.

---

## 6. WSGI Configuration File

1. On the **Web** tab, click the link to your **WSGI configuration file** (e.g., `/var/www/<username>_pythonanywhere_com_wsgi.py`).
2. Delete the default contents and paste the following configuration:

```python
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. Add application directory to sys.path
project_home = os.path.expanduser('~/passli')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 2. Load environment variables from ~/.env outside the repository
env_path = Path(os.path.expanduser('~/.env'))
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# 3. Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

# 4. Initialize Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```
3. Save the file.

---

## 7. Reload Web App

Return to the **Web** tab and click the green **Reload <username>.pythonanywhere.com** button.

Your application is now live at `https://<username>.pythonanywhere.com`.

---

## 8. Post-Deployment Verification Checklist

Execute this verification sequence to confirm end-to-end functionality and security isolation:

- [ ] **Account Registration & OTP**: Visit `https://<username>.pythonanywhere.com/accounts/register/`. Register a test account and verify that the 6-digit OTP verification code is received in your inbox.
- [ ] **Ciphertext-at-Rest Inspection**: Log in, upload a test PDF or image (`upload.html`), and inspect the stored file in the Bash console:
  ```bash
  head -c 64 ~/passli/media/vault_files/*
  ```
  Confirm the file contains raw encrypted binary ciphertext with AES-256-GCM authentication tags, rather than plaintext.
- [ ] **Direct Media 404 Verification**: Verify in a browser or curl that direct media access is blocked:
  ```bash
  curl -I https://<username>.pythonanywhere.com/media/vault_files/test.pdf
  ```
  Expect HTTP **404 Not Found**.
- [ ] **Rate Limiting & Lockout Verification**: Create a Share Pass, visit the recipient verification link, and submit invalid Share Keys until lockout (5 failures). Test with a forged proxy header:
  ```bash
  curl -I -H "X-Forwarded-For: 203.0.113.199" -X POST -d "access_key=WRONGKEY" https://<username>.pythonanywhere.com/p/<pass-uuid>/
  ```
  Confirm HTTP **429 Too Many Requests** is returned after the threshold.
- [ ] **Security Audit Feed**: Log into `https://<username>.pythonanywhere.com/admin-dashboard/audit/` as superadmin. Confirm that failed verification attempts and actual client IP addresses are accurately recorded.

---

## 9. Application Updates Procedure

When updating Passli in the future:

```bash
cd ~/passli
set -a; source ~/.env; set +a

# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Collect static assets
python manage.py collectstatic --noinput
```

After updating, visit the **Web** tab and click **Reload**.

---

## 10. Gmail SMTP Setup Runbook

PythonAnywhere free accounts have restricted outbound internet access, but permit connections to Gmail's SMTP servers on port 587 via an official firewall exception.

1. Use a **dedicated Gmail account** for application notifications (e.g. `your-app-notify@gmail.com`).
2. Go to [Google Account Security](https://myaccount.google.com/security) and ensure **2-Step Verification** is enabled.
3. Visit [Google App Passwords](https://myaccount.google.com/apppasswords).
4. Enter an app name (e.g. `Passli PythonAnywhere`) and click **Create**.
5. Copy the generated 16-character code (without spaces) and paste it into `SMTP_PASS` in `~/.env`.
6. Set `SMTP_PORT=587`.
7. **Security Rule**: Never use your primary Google account password. If you suspect an app password was exposed, revoke it immediately from the Google security dashboard.

---

## 11. Known Hosting Limits on PythonAnywhere Free Tier

Keep the following operational constraints in mind:

- **512 MB Storage Limit**: The 512 MB quota covers your virtual environment, source code, SQLite database (`db.sqlite3`), and uploaded vault files (`media/`). Check storage regularly on your PythonAnywhere dashboard.
- **Single Web App**: Free accounts support exactly one hosted web application.
- **Restricted Outbound Internet**: Only outbound connections to hosts on PythonAnywhere's whitelist are permitted. Gmail SMTP (`smtp.gmail.com:587`) is whitelisted.
- **No Docker**: PythonAnywhere runs on standard Linux virtualenvs; Docker is not available.
- **3-Month Expiry**: Free web apps require manual renewal every 3 months. Click the **Run until 3 months from today** button on the Web tab periodically.
