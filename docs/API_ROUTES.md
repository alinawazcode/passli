# Passli Route & Endpoint Specification Reference

This document provides a complete catalog of all URL endpoints, view handlers, access controls, and expected responses across the Passli platform.

---

## 1. Authentication & Account Management (`accounts/`)

| Path | View | Method | Auth Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/` | `landing_view` | GET | No | Public landing page with live interactive cryptographic sandbox |
| `/register/` | `register_view` | GET, POST | No | Account registration; creates inactive user and sends OTP |
| `/verify-email/` | `verify_email_view` | GET, POST | Yes (Pending OTP) | Validates 6-digit email OTP and activates user account |
| `/verify-email/resend/` | `resend_verification_otp_view` | POST | Yes (Pending OTP) | Generates and sends a fresh 6-digit OTP code |
| `/login/` | `CustomLoginView` | GET, POST | No | Authenticates user; redirects to `/dashboard/` |
| `/logout/` | `CustomLogoutView` | POST | Yes | CSRF-protected session teardown; redirects to landing |
| `/password-reset/` | `password_reset_request_view` | GET, POST | No | Accepts email and dispatches cryptographic reset link |
| `/password-reset/confirm/<token>/` | `password_reset_confirm_view` | GET, POST | No | Validates one-time token and updates account password |
| `/dashboard/` | `dashboard_view` | GET | Yes | Personal vault overview with metric telemetry cards |

---

## 2. Document Vault Management (`documents/`)

| Path | View | Method | Auth Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/documents/` | `documents_list_view` | GET | Yes | Filterable document vault list with category chips |
| `/documents/upload/` | `documents_upload_view` | GET, POST | Yes | AES-256-GCM upload dropzone and metadata form |
| `/documents/<id>/` | `document_detail_view` | GET | Yes (Owner) | Document detail view with SHA-256 digest & metadata |
| `/documents/<id>/preview/` | `document_preview_view` | GET | Yes (Owner) | In-memory decrypted document stream (inline view) |
| `/documents/<id>/download/` | `document_download_view` | GET | Yes (Owner) | In-memory decrypted document stream (attachment) |
| `/documents/<id>/edit/` | `document_edit_view` | GET, POST | Yes (Owner) | Updates document title, category, and notes |
| `/documents/<id>/delete/` | `document_delete_view` | POST | Yes (Owner) | Removes database record and encrypted file from disk |

---

## 3. Ephemeral Sharing Management (`sharing/`)

| Path | View | Method | Auth Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/share/` | `share_list_view` | GET | Yes | Active and expired Share Passes list |
| `/share/create/` | `share_create_view` | GET, POST | Yes | Multi-document pass generator with TTL selection |
| `/share/<uuid>/` | `share_detail_view` | GET | Yes (Owner) | Pass telemetry, QR code display, and 8-character key |
| `/share/<uuid>/revoke/` | `share_revoke_view` | POST | Yes (Owner) | 1-click immediate pass revocation |
| `/share/<uuid>/qr/download/` | `share_qr_download_view` | GET | Yes (Owner) | Downloads isolated PNG image of the pass QR code |

---

## 4. Recipient Public Gateway (`sharing/recipient_urls.py`)

| Path | View | Method | Auth Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/p/<uuid>/` | `recipient_verify_view` | GET, POST | Public (Rate-limited) | 8-character Share Key entry portal; enforces lockout |
| `/p/<uuid>/portal/` | `recipient_portal_view` | GET | Verified Session | Recipient document viewer with countdown timer |
| `/p/<uuid>/doc/<id>/preview/` | `recipient_doc_preview_view` | GET | Verified Session | In-memory decrypted stream for verified recipient |
| `/p/<uuid>/doc/<id>/download/`| `recipient_doc_download_view`| GET | Verified Session | Decrypted file download (only if pass grants download) |
| `/p/<uuid>/leave/` | `recipient_leave_view` | POST | Verified Session | Recipient session exit; clears session authentication |

---

## 5. Security & Audit Trail (`audit/`)

| Path | View | Method | Auth Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/audit/` | `audit_list_view` | GET | Yes | Chronological audit trail of pass unlocks and previews |

---

## 6. Superadmin Governance Console (`accounts/admin_urls.py`)

| Path | View | Method | Auth Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/admin-dashboard/` | `admin_dashboard_overview` | GET | Superadmin | Telemetry cards, storage breakdown, and threat feed |
| `/admin-dashboard/users/` | `admin_dashboard_users` | GET | Superadmin | User directory with search and quota inspection |
| `/admin-dashboard/users/<id>/toggle-status/` | `admin_user_toggle_status` | POST | Superadmin | Toggles user account activation status |
| `/admin-dashboard/documents/`| `admin_dashboard_documents`| GET | Superadmin | Global document repository with SHA-256 inspection |
| `/admin-dashboard/documents/<id>/delete/` | `admin_document_delete` | POST | Superadmin | Physical disk file cleanup and database record purge |
| `/admin-dashboard/passes/` | `admin_dashboard_passes` | GET | Superadmin | System-wide pass monitor |
| `/admin-dashboard/passes/<uuid>/revoke/` | `admin_pass_revoke` | POST | Superadmin | Emergency system-wide pass revocation |
| `/admin-dashboard/audit/` | `admin_dashboard_audit` | GET | Superadmin | Global threat feed with IP search and lockout filters |
