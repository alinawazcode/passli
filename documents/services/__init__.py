"""
Document Vault Services Package.
"""
from .crypto_service import (
    encrypt_bytes,
    decrypt_bytes,
    get_vault_master_key,
    generate_vault_master_key,
    VaultDecryptionError,
)

__all__ = [
    'encrypt_bytes',
    'decrypt_bytes',
    'get_vault_master_key',
    'generate_vault_master_key',
    'VaultDecryptionError',
]
