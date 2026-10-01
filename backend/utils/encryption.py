"""
Encryption utilities for sensitive data (e.g., PDF passwords).
Uses Fernet symmetric encryption (AES-128-CBC) from the cryptography library.

The encryption key is derived from SECRET_KEY in settings so no extra env var is needed.
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from backend.config import settings


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the application SECRET_KEY (deterministic)."""
    # SHA-256 of SECRET_KEY gives 32 bytes → base64url-encode for Fernet
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_password(plaintext: str) -> str:
    """Encrypt a plaintext PDF password. Returns base64 ciphertext string."""
    if not plaintext:
        return plaintext
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    """Decrypt a ciphertext PDF password. Returns plaintext string."""
    if not ciphertext:
        return ciphertext
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()
