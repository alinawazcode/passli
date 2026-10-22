# Passli — Cryptographic Document Vault & Ephemeral Sharing Platform

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.1%2B-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-100%25%20passing-brightgreen.svg)](tests/)
[![Security: Zero-Knowledge](https://img.shields.io/badge/security-Zero--Knowledge-informational.svg)](SECURITY.md)

**Passli** is an enterprise-grade, privacy-first personal records vault and ephemeral cryptographic sharing platform. It enables individuals and organizations to share sensitive documents (e.g., medical records, identity credentials, diplomas, vehicle papers) with recipients via time-gated **Share Passes** without exposing master cloud credentials, unencrypted email attachments, or cascading folder permissions.

---

## 🔒 The Problem Passli Solves

When sharing sensitive records with doctors, employers, financial institutions, or rental agencies, users are traditionally forced to:
1. **Send raw email attachments** that persist indefinitely across mail relays and recipient drives.
2. **Share master cloud storage links** (e.g., Google Drive, Dropbox), risking account leakage and folder cascading.
3. **Hand over unlocked physical devices** to third parties.

**Passli replaces these vulnerabilities with time-gated, cryptographic Share Passes.** You select specific records, define an expiration window (15m, 30m, 1h, 2h, 24h, or 1-time view), set download or view-only constraints, and present an isolated QR code and 8-character Share Key. When the session expires or is revoked by the owner, recipient access is mathematically severed.

---

## ✨ Core Platform Features

### 🗄️ 1. Personal Document Vault
- **Domain Taxonomy**: Organize records into structured categories (`Medical`, `Education`, `Vehicle`, `Personal & Identity`, `Professional`, `Other`).
- **Cryptographic Integrity**: Automatic SHA-256 binary hash digests computed on ingestion for tamper validation.
- **In-Browser Secure Preview**: Stream decrypted PDF documents and high-resolution image records safely without local disk leakage.

### 🔑 2. Cryptographic Share Passes & Ephemeral QR Protocol
- **Zero-Knowledge Key Storage**: Plaintext 8-character Share Keys (`XXXX-XXXX`) are never saved to disk; only salted PBKDF2 hashes are stored.
- **Two-Factor Access Guard**: Decryption requires scanning the isolated session URL **plus** entering the valid Share Key.
- **Granular Permissions**: Restrict recipients to in-browser viewing only or grant file download permissions.
- **Server-Enforced Expirations**: Hardware session termination on timer expiry (15 min to 24 hrs) or burn-after-reading 1-time access.
- **Immediate 1-Click Revocation**: Instantly terminate any active pass and sever recipient sessions in real-time.

### 📱 3. Responsive Recipient Portal
- **Mobile-First Experience**: Optimized for smartphones scanning QR codes, with swipeable document selector chips and touch-friendly viewers.
- **Session Countdown Timer**: Real-time ticker notifying recipients of remaining access duration.
- **Memory Wipe on Exit**: Explicit session termination button clearing decrypted in-browser memory.

### 🛡️ 4. Security & Audit Threat Feed
- **Structured Audit Logging**: Immutable access trail recording IP addresses, user agents, verification successes, failed attempts, and brute-force lockouts.
- **Rate-Limiting & Lockouts**: Exponential backoff and lockouts protecting share passes against automated brute-force attempts.

### ⚡ 5. Custom Platform Administration Console
- **System Telemetry & Storage Analytics**: Real-time storage consumption (MB/GB), category breakdown bars, and active pass monitors at `/admin-dashboard/`.
- **User Governance**: Searchable user management directory with quota inspection, account activation toggles, and staff role promotions.
- **Global File Inventory**: Platform-wide vault explorer with SHA-256 hash inspection and physical disk file cleanup.
- **Emergency Pass Governance**: System-wide pass monitor with instant emergency revocation capabilities.

---

## 📊 Security Architecture Comparison

| Specification | Passli Share Pass | Cloud Shared Folders | Email Attachments |
| :--- | :--- | :--- | :--- |
| **Encryption Standard** | Client-isolated AES-256 + PBKDF2 key hashing | Server-side at rest only | Unencrypted MIME transit |
| **Credential Exposure** | **Zero exposure** (Ephemeral session) | Exposes folder trees & account metadata | Permanent static copies on recipient host |
| **Session Expiration** | **Strict server & hardware timer** | Manual disabling; indefinite persistence | Impossible; persists forever in inboxes |
| **Granular Access** | **Itemized per-pass document bundling** | All-or-nothing folder cascades | Detached static payloads |
| **Audit Visibility** | **Real-time structured access logs & IP feed** | Basic access history (Enterprise only) | Zero visibility after send |

---

## 🏗️ Project Architecture

```text
passli/
├── accounts/          # User authentication, profiles, superadmin governance & telemetry
│   ├── admin_views.py # Custom Platform Admin Console views & metric aggregations
│   ├── admin_urls.py  # Admin dashboard routing (/admin-dashboard/)
│   └── views.py       # User signin, registration, profile views
├── documents/         # Document vault, file encryption models, categorization
│   ├── models.py      # Document model with SHA-256 digest computation
│   └── views.py       # Vault listing, upload handler, secure stream preview
├── sharing/           # Share Pass generation, cryptographic verification & recipient portal
│   ├── models.py      # SharePass model with PBKDF2 hash validation
│   ├── recipient_views.py # Public recipient authentication & session portal
│   └── utils.py       # QR code generator & 8-character key generator
├── audit/             # Structured security event logging & immutable audit trail
│   ├── models.py      # ShareAccessLog model & log_share_event utility
│   └── views.py       # User audit history feed & filtering
├── config/            # Django settings, WSGI/ASGI handlers, global URL configuration
├── templates/         # Semantic HTML5 templates (Vanilla CSS & Material Symbols)
│   ├── administration/# Custom Admin Console templates (overview, users, documents, passes, audit)
│   ├── sharing/       # Recipient verify, portal, and create templates
│   └── base.html      # Master responsive layout with glassmorphic navbar
├── static/            # Human-crafted Vanilla CSS (styles.css) & client JS (main.js)
├── tests/             # Comprehensive unit test suites (Auth, Documents, Sharing, Audit, Security)
├── Procfile           # Production Gunicorn deployment process
├── railway.json       # Railway PaaS deployment configuration
└── manage.py          # Django CLI management entry point
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- **Python**: 3.11 or 3.12
- **Git**
- **pip** and **virtualenv**

### 2. Clone the Repository
```bash
git clone https://github.com/Ali-Nawaz-devt/passli.git
cd passli
```

### 3. Setup Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
```bash
# Copy sample environment configuration
cp .env.example .env
```
Key `.env` configuration options:
```env
DEBUG=True
SECRET_KEY=your-secure-django-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=YourStrongPassword123!
DJANGO_SUPERUSER_EMAIL=admin@passli.dev
```

### 6. Database Migrations & Initial Superuser
```bash
python manage.py migrate
python manage.py ensure_superadmin
python manage.py collectstatic --no-input
```

### 7. Run Local Development Server
```bash
python manage.py runserver
```
Navigate to `http://localhost:8000/` in your browser.

---

## 🧪 Automated Testing

Passli enforces strict automated test verification across all platform features.

```bash
# Run entire test suite
python manage.py test

# Run administration test suite
python manage.py test tests.unit.test_administration

# Run tests with verbose output
python manage.py test -v 2
```

---

## 🚢 Deployment (Railway & PaaS)

Passli is production-ready for deployment on **Railway**, **Render**, **Fly.io**, or **Heroku**.

1. Connect your GitHub repository to Railway.
2. Railway detects `railway.json` and `Procfile` automatically.
3. The build executes:
   ```bash
   python manage.py migrate && python manage.py ensure_superadmin && python manage.py collectstatic --no-input && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```
4. Configure production environment variables (`SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DEBUG=False`).

---

## 🛡️ Security & Responsible Disclosure

Security and cryptographic isolation are core to Passli. For vulnerability disclosure guidelines, threat models, and cryptographic parameters, please refer to [SECURITY.md](SECURITY.md) or contact **[alinawaz.code@gmail.com](mailto:alinawaz.code@gmail.com)**.

---

## 🤝 Contributing

Contributions, bug reports, and feature proposals are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a pull request.

---

## 📬 Authors & Maintainers

For project inquiries, partnerships, enterprise deployments, or general questions, connect with the project maintainers:

- **Ali Nawaz** — Lead Architecture & Backend Engineering &bull; [@alinawazcode](https://github.com/alinawazcode)
- **Muqadas Fareed** — Co-Author & Project Maintainer &bull; [@Muqadas-Fareed-devt](https://github.com/Muqadas-Fareed-devt)
- **Email Contact**: [alinawaz.code@gmail.com](mailto:alinawaz.code@gmail.com)
- **Live Demo**: [https://web-production-c1bd05e.up.railway.app](https://web-production-c1bd05e.up.railway.app)

---

## 📄 License

This project is open-source and licensed under the [MIT License](LICENSE).

