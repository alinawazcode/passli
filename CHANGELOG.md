# Changelog

All notable changes to the **Passli** project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0] - 2026-10-23

### Added
- **Cryptographic Envelope Hardening & AAD Binding**:
  - Bound document UUID as Associated Data (AAD) in AES-256-GCM AEAD encryption, preventing ciphertext swap and cross-tenant tampering.
  - Zero-downtime key rotation architecture supporting `VAULT_KEY_VERSION` and `VAULT_MASTER_KEY_PREVIOUS`.
  - Added `--reencrypt-legacy` and `--force` flags to `encrypt_vault_storage` management command.
- **Transactional Email Infrastructure & Automated Security Alerts**:
  - Direct Gmail / custom SMTP service with TLS/SSL auto-negotiation (`EMAIL_USE_SSL` / `EMAIL_USE_TLS`).
  - 6-digit numeric OTP code dispatch for user email registration verification.
  - Cryptographic single-use token links for secure password reset workflows.
  - Automated brute-force QR passcode alert emails triggered after 5 consecutive failed verification attempts.
  - Added `python manage.py test_smtp [recipient]` CLI diagnostic for connectivity verification.
- **Persistent Database Rate-Limiting & Lockout Defense**:
  - Atomic transaction tracking per pass and IP address using `select_for_update()`.
  - Exponential backoff lockout (1 minute initial, doubling up to 24 hours) returning standard `HTTP 429` with `Retry-After` headers.
  - Standardized client IP extraction via `TRUSTED_PROXY_COUNT` with strict RFC 5737 and PostgreSQL `inet` data type compliance.
- **Superadmin Auto-Provisioning**:
  - Idempotent `ensure_superadmin` command supporting both primary and optional secondary superuser accounts (`DJANGO_SECONDARY_SUPERUSER_*`).
- **Selenium 4 Automated Presentation Testing Suite (`selenium_presentation_suite/`)**:
  - Standalone presentation test suite with 16 end-to-end lifecycle test cases (TC01–TC16) and 3 controlled negative demonstration tests.
  - Thread-safe desktop Tkinter GUI dashboard with live telemetry, progress tracking, and pacing slowdown controls (Slow Process, Narration, Ultra Slow).
  - Persistent Chrome window mode (`KEEP_BROWSER_OPEN = True`) for live presentation and recording without browser restarts.
  - Standalone dark-mode HTML test execution report generation (`report.html`) and automated timestamped screenshots.
- **Hardened Continuous Integration (CI/CD)**:
  - Multi-stage GitHub Actions workflow testing across PostgreSQL 16 service containers.
  - Automated Ruff code quality linter and pip-audit vulnerability scanning.
  - Automated Docker image build validation.
  - Test suite coverage gate enforcing >= 80% coverage on every push and pull request.

### Fixed
- Fixed PostgreSQL `DataError: invalid input syntax for type inet` in lockout unit tests by standardizing on RFC 5737 test IP blocks.
- Fixed duplicate cryptographic key generation steps in GitHub Actions CI workflow.
- Updated security claims and documentation to reflect architectural transparency (server-side AES-256-GCM encryption with server-held master key).

---

## [1.2.0] - 2026-10-01

### Added
- **Custom Platform Administration Console (`/admin-dashboard/`)**:
  - Live system telemetry cards for active users, storage usage (MB/GB), active share passes, and security threats.
  - Storage consumption breakdown across domain taxonomies (Medical, Identity, Education, Vehicle, Professional).
  - User accounts management directory with activation/deactivation toggles and staff promotions.
  - Platform-wide document repository with SHA-256 hash inspection and physical disk file cleanup.
  - Share pass monitor with one-click emergency revocation.
  - Global security threat feed with IP search, event filtering, and brute-force lockout monitors.
- **Mobile-Responsive Recipient Portal**:
  - Full touch and phone responsiveness on QR code recipient pages (`/p/<pass_id>/` and `/p/<pass_id>/portal/`).
  - Auto-formatted 8-character Share Key input with 18px+ mobile font to prevent auto-zoom distortion.
  - Horizontal swipeable document selector chips on tablet and smartphone viewports.
  - Viewport-scaled PDF and image canvas with touch scrolling.
- **Seamless Document Upload Flow**:
  - Added return redirect (`?next=share_create`) so uploading a document directly resumes pass creation.
  - Added URL pattern aliases for `document_upload` and `documents_upload`.

### Fixed
- Fixed navbar text wrapping on desktop viewports.
- Fixed `NoReverseMatch` error on empty-state pass creation.
- Aligned top navigation with Passli's clean dark navy enterprise design system.

---

## [1.1.0] - 2026-09-27

### Added
- **Audit Trail & Threat Feed**:
  - Immutable event logging (`ShareAccessLog`) for key verification, document previews, and download streams.
  - Brute-force lockout and rate-limiting defenses.
  - User-facing audit dashboard with timestamped security events and IP tracking.
- **Automated Verification & E2E Testing**:
  - Comprehensive unit test coverage across all core modules.
  - Integration testing and security audit suites.

---

## [1.0.0] - 2026-09-22

### Added
- **Initial Release & Core Protocol**:
  - Document vault with AES-256-GCM encryption and SHA-256 digest computation.
  - Categorization into Medical, Education, Vehicle, Personal, and Professional records.
  - Ephemeral Share Pass generation with isolated QR codes and 8-character PBKDF2 Share Keys.
  - Time-gated session termination and 1-click immediate owner revocation.
  - Modern, responsive Vanilla CSS design system.
