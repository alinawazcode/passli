# Security Policy & Cryptographic Architecture

Passli is engineered with an ephemeral, privacy-first access control architecture designed for secure, time-gated document sharing without master credential exposure.

---

## 🛡️ Supported Versions

We actively support and release security updates for the following versions of Passli:

| Version | Supported | Security Maintenance |
| :--- | :--- | :--- |
| `1.x.x` (Current Main) | :white_check_mark: | Active Security Patches |
| `< 1.0.0` | :x: | Deprecated |

---

## 🔒 Security Specifications & Threat Model

1. **Ephemeral Key Access Control**:
   - Plaintext 8-character Share Keys (`XXXX-XXXX`) are generated dynamically using cryptographically secure random sources (`secrets.choice` from a 31-character unambiguous alphabet).
   - Plaintext keys are **never stored** in the database or written to server logs; only salted **PBKDF2-HMAC-SHA256** hashes are retained (`django.contrib.auth.hashers.make_password`).
   - The server verifies submitted keys against the PBKDF2 hash using constant-time comparison to establish ephemeral, session-bound recipient access.

2. **Storage Architecture & Server-Side Security**:
   - Uploaded vault documents are stored on server-side media storage (with randomized UUID filenames preventing path traversal) and served strictly through authenticated view endpoints with `X-Content-Type-Options: nosniff` and `no-store` cache controls.
   - *Note on Threat Model*: Passli enforces strict server-side multi-tenant access controls, IDOR defenses, and time-gated authorization tokens. It is not currently a client-side end-to-end zero-knowledge system; files are stored in server-managed storage.

3. **Binary Digest Integrity**:
   - Every uploaded vault document is processed through **SHA-256** checksum hashing on ingestion.
   - Binary digests allow instant verification of document integrity and detect unauthorized alteration or corrupted uploads.

4. **Multi-Tenant IDOR Protection**:
   - All vault access handlers strictly filter by `user=request.user` or authenticated session ID before serving document contents.
   - Direct object reference tampering is caught at the view boundary with HTTP 404/403 responses.

5. **Brute-Force & Rate-Limiting Defenses**:
   - Failed Share Key attempts trigger structured security logs and increment attempt counters.
   - Excess attempts enforce exponential lockouts to defeat automated credential stuffing and key enumeration.

6. **Server-Enforced Expiration & Revocation**:
   - Expiration timestamps (`expires_at`) and single-use usage limits (`max_uses`) are atomically validated on recipient verification requests.
   - When a pass expires or is revoked, access is immediately terminated, and session memory is wiped.

7. **Structured Audit Logging**:
   - Access events are recorded in an application-level append-only relational audit table (`ShareAccessLog`), capturing client IP, user agent, event type, and outcome timestamp for owner visibility.


---

## 🚨 Reporting a Vulnerability

If you discover a potential security vulnerability within Passli, please **do not open a public issue**. Instead, follow our responsible disclosure procedure:

1. Send an email with full reproduction steps to: **`alinawaz.code@gmail.com`**
2. Include the following details in your report:
   - Description of the vulnerability and its potential impact.
   - Step-by-step instructions or proof-of-concept (PoC) code.
   - Affected URLs, endpoints, or parameters.
   - Suggestions for mitigation or fix (optional).

### Response Timeline
- **Initial Acknowledgment**: Within 24 hours.
- **Vulnerability Assessment**: Within 48 hours.
- **Patch & Release**: Within 7 business days for critical vulnerabilities.

We credit all responsible security researchers in our release notes and Hall of Fame.
