# Changelog

All notable changes to the **Passli** project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
