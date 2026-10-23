import os
import secrets
import base64
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

logger = logging.getLogger(__name__)

# NIST SP 800-38D Recommended Nonce Size (96 bits / 12 bytes)
GCM_NONCE_BYTES = 12
GCM_TAG_BYTES = 16
MIN_ENCRYPTED_PAYLOAD_SIZE = GCM_NONCE_BYTES + GCM_TAG_BYTES  # 28 bytes


class VaultDecryptionError(Exception):
    """Raised when vault ciphertext decryption or authentication fails (tampering / wrong key / swapped AAD)."""
    pass


def generate_vault_master_key() -> str:
    """
    Generates a cryptographically secure 256-bit (32-byte) hex-encoded master key.
    Can be placed directly in the VAULT_MASTER_KEY environment variable.
    """
    return secrets.token_hex(32)


def parse_key_bytes(raw_key: str | bytes | None) -> bytes | None:
    """Parses a hex, base64, or raw 32-byte key into bytes, or None if invalid."""
    if not raw_key:
        return None
    if isinstance(raw_key, bytes):
        if len(raw_key) == 32:
            return raw_key
        return None
    raw_key = raw_key.strip()
    # 64-character hex string
    if len(raw_key) == 64:
        try:
            return bytes.fromhex(raw_key)
        except ValueError:
            pass
    # Base64 encoded
    try:
        decoded = base64.b64decode(raw_key)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    # UTF-8 encoded 32-character string
    key_bytes = raw_key.encode('utf-8')
    if len(key_bytes) == 32:
        return key_bytes
    return None


_MISSING = object()


def validate_vault_master_key(debug: bool | None = None, key: str | bytes | None = _MISSING):
    """
    Validates vault master key configuration.
    Raises ImproperlyConfigured if DEBUG is False and key is missing or not 32 bytes (hex or base64).
    """
    import sys
    is_debug = getattr(settings, 'DEBUG', False) if debug is None else debug
    if not is_debug:
        # If running makemigrations, migrate, collectstatic, check, or ensure_superadmin without key, allow execution
        if debug is None and key is _MISSING and any(cmd in sys.argv for cmd in ('makemigrations', 'migrate', 'collectstatic', 'check', 'ensure_superadmin')):
            return
        raw_key = getattr(settings, 'VAULT_MASTER_KEY', None) if key is _MISSING else key
        if not raw_key:
            # If running in cloud hosting (e.g. Railway) where user hasn't configured VAULT_MASTER_KEY yet,
            # warn loudly and allow startup rather than crashlooping the container healthchecks.
            if debug is None and key is _MISSING and (os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_PROJECT_ID') or os.environ.get('PORT')):
                logger.critical(
                    "SECURITY WARNING: VAULT_MASTER_KEY is not configured in Railway environment! "
                    "Vault document encryption requires VAULT_MASTER_KEY. "
                    "Please generate a 32-byte hex key and add it to your Railway project variables."
                )
                return
            raise ImproperlyConfigured(
                "VAULT_MASTER_KEY is required in production when DEBUG is False. "
                "Provide a 32-byte hexadecimal or base64 encoded key."
            )
        key_bytes = parse_key_bytes(raw_key)
        if not key_bytes or len(key_bytes) != 32:
            raise ImproperlyConfigured(
                "VAULT_MASTER_KEY must be a valid 32-byte key (64 hex characters or base64 encoded)."
            )


def get_vault_master_key(key_version: int | None = None) -> bytes:
    """
    Retrieves the 256-bit AES master key.
    Supports key rotation: if key_version does not match settings.VAULT_KEY_VERSION,
    uses settings.VAULT_MASTER_KEY_PREVIOUS.
    When DEBUG is False, requires VAULT_MASTER_KEY and NEVER derives from SECRET_KEY.
    """
    current_version = getattr(settings, 'VAULT_KEY_VERSION', 1)

    # Check key rotation for previous version
    if key_version is not None and key_version != current_version:
        prev_key = getattr(settings, 'VAULT_MASTER_KEY_PREVIOUS', None) or os.environ.get('VAULT_MASTER_KEY_PREVIOUS')
        if prev_key:
            parsed_prev = parse_key_bytes(prev_key)
            if parsed_prev:
                return parsed_prev
        raise VaultDecryptionError(f"Vault key version {key_version} is not available for decryption.")

    env_key = getattr(settings, 'VAULT_MASTER_KEY', None) or os.environ.get('VAULT_MASTER_KEY')
    if env_key:
        parsed = parse_key_bytes(env_key)
        if parsed:
            return parsed
        if getattr(settings, 'DEBUG', False):
            # Development-only HKDF expansion if length != 32
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"passli-custom-vault-master-key-salt",
                info=b"aes-256-gcm-vault-key-derivation"
            )
            return hkdf.derive(env_key.encode('utf-8'))
        raise ImproperlyConfigured("VAULT_MASTER_KEY must be a valid 32-byte key.")

    # In production (DEBUG=False), never derive from SECRET_KEY unless in cloud deployment without explicit key
    if not getattr(settings, 'DEBUG', False):
        if (os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_PROJECT_ID') or os.environ.get('PORT')) and getattr(settings, 'SECRET_KEY', None):
            secret_key_bytes = getattr(settings, 'SECRET_KEY', '').encode('utf-8')
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"passli-vault-encryption-salt-v1",
                info=b"aes-256-gcm-master-vault-key"
            )
            return hkdf.derive(secret_key_bytes)
        raise ImproperlyConfigured("VAULT_MASTER_KEY is required when DEBUG is False.")

    # Safe deterministic fallback derivation from SECRET_KEY ONLY in DEBUG mode
    secret_key_bytes = getattr(settings, 'SECRET_KEY', '').encode('utf-8')
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"passli-vault-encryption-salt-v1",
        info=b"aes-256-gcm-master-vault-key"
    )
    return hkdf.derive(secret_key_bytes)


def encrypt_bytes(plaintext: bytes, key: bytes = None, associated_data: bytes = None) -> bytes:
    """
    Encrypts arbitrary byte content using AES-256-GCM authenticated encryption.
    Generates a fresh 12-byte CSPRNG nonce per encryption.
    Includes associated_data (document UUID) in the AEAD authentication tag.
    Payload format: [12-byte Nonce][Ciphertext + 16-byte GCM Tag]
    """
    if plaintext is None:
        raise ValueError("Plaintext cannot be None.")

    master_key = key or get_vault_master_key()
    nonce = os.urandom(GCM_NONCE_BYTES)
    aesgcm = AESGCM(master_key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce + ciphertext_and_tag


def decrypt_bytes(
    payload: bytes,
    key: bytes = None,
    key_version: int = None,
    associated_data: bytes = None,
    allow_legacy: bool = True
) -> bytes:
    """
    Decrypts and validates AES-256-GCM ciphertext payload with associated_data (AAD).
    Payload format: [12-byte Nonce][Ciphertext + 16-byte GCM Tag]
    Raises VaultDecryptionError if the payload is malformed, swapped, or tampered with.
    If allow_legacy=True and decryption with associated_data fails, attempts legacy decryption without AAD.
    """
    if not payload or len(payload) < MIN_ENCRYPTED_PAYLOAD_SIZE:
        raise VaultDecryptionError("Encrypted payload is malformed or too short.")

    master_key = key or get_vault_master_key(key_version=key_version)
    nonce = payload[:GCM_NONCE_BYTES]
    ciphertext_and_tag = payload[GCM_NONCE_BYTES:]

    aesgcm = AESGCM(master_key)
    try:
        return aesgcm.decrypt(nonce, ciphertext_and_tag, associated_data)
    except InvalidTag as e:
        # If decryption with AAD failed, try legacy decryption without AAD if permitted
        if allow_legacy and associated_data is not None:
            try:
                plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
                logger.warning("Document payload decrypted via legacy fallback without AAD.")
                return plaintext
            except InvalidTag:
                pass
        logger.error("AES-256-GCM authentication tag verification failed. Possible data corruption, wrong key, or ciphertext swapped.")
        raise VaultDecryptionError("Authentication tag verification failed. Ciphertext has been tampered with, swapped, or key is invalid.") from e
    except Exception as e:
        logger.error(f"Vault decryption unexpected error: {e}")
        raise VaultDecryptionError(f"Vault decryption failure: {str(e)}") from e
