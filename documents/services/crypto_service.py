import os
import secrets
import base64
import logging
from django.conf import settings
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
    """Raised when vault ciphertext decryption or authentication fails (tampering / wrong key)."""
    pass


def generate_vault_master_key() -> str:
    """
    Generates a cryptographically secure 256-bit (32-byte) hex-encoded master key.
    Can be placed directly in the VAULT_MASTER_KEY environment variable.
    """
    return secrets.token_hex(32)


def get_vault_master_key() -> bytes:
    """
    Retrieves the 256-bit AES master key.
    Precedence:
    1. settings.VAULT_MASTER_KEY (hex or base64 or raw bytes)
    2. Derived deterministically from settings.SECRET_KEY via HKDF-SHA256 (safe fallback for testing/dev)
    """
    env_key = getattr(settings, 'VAULT_MASTER_KEY', None) or os.environ.get('VAULT_MASTER_KEY')
    if env_key:
        env_key = env_key.strip()
        # 64-character hex string
        if len(env_key) == 64:
            try:
                return bytes.fromhex(env_key)
            except ValueError:
                pass
        # 32 raw bytes string or base64 encoded
        try:
            decoded = base64.b64decode(env_key)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        # UTF-8 encoded 32-character string
        key_bytes = env_key.encode('utf-8')
        if len(key_bytes) == 32:
            return key_bytes

        # If length != 32, derive 32 bytes using HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"passli-custom-vault-master-key-salt",
            info=b"aes-256-gcm-vault-key-derivation"
        )
        return hkdf.derive(key_bytes)

    # Deterministic fallback derivation from SECRET_KEY
    secret_key_bytes = getattr(settings, 'SECRET_KEY', '').encode('utf-8')
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"passli-vault-encryption-salt-v1",
        info=b"aes-256-gcm-master-vault-key"
    )
    return hkdf.derive(secret_key_bytes)


def encrypt_bytes(plaintext: bytes, key: bytes = None) -> bytes:
    """
    Encrypts arbitrary byte content using AES-256-GCM authenticated encryption.
    Generates a fresh 12-byte CSPRNG nonce per encryption.
    Payload format: [12-byte Nonce][Ciphertext + 16-byte GCM Tag]
    """
    if plaintext is None:
        raise ValueError("Plaintext cannot be None.")

    master_key = key or get_vault_master_key()
    nonce = os.urandom(GCM_NONCE_BYTES)
    aesgcm = AESGCM(master_key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext_and_tag


def decrypt_bytes(payload: bytes, key: bytes = None) -> bytes:
    """
    Decrypts and validates AES-256-GCM ciphertext payload.
    Payload format: [12-byte Nonce][Ciphertext + 16-byte GCM Tag]
    Raises VaultDecryptionError if the payload is malformed or tampered with.
    """
    if not payload or len(payload) < MIN_ENCRYPTED_PAYLOAD_SIZE:
        raise VaultDecryptionError("Encrypted payload is malformed or too short.")

    master_key = key or get_vault_master_key()
    nonce = payload[:GCM_NONCE_BYTES]
    ciphertext_and_tag = payload[GCM_NONCE_BYTES:]

    aesgcm = AESGCM(master_key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
        return plaintext
    except InvalidTag as e:
        logger.error("AES-256-GCM authentication tag verification failed. Possible data corruption or tampering.")
        raise VaultDecryptionError("Authentication tag verification failed. Ciphertext has been tampered with or key is invalid.") from e
    except Exception as e:
        logger.error(f"Vault decryption unexpected error: {e}")
        raise VaultDecryptionError(f"Vault decryption failure: {str(e)}") from e
