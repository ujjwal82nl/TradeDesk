"""Utility: Encrypt/decrypt broker tokens using Fernet symmetric encryption."""
import base64
import os
from cryptography.fernet import Fernet
from app.core.config import settings


def _get_fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        # Generate and warn - in production this must be set
        key = Fernet.generate_key().decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_token(token: str) -> str:
    """Encrypt a broker token for storage."""
    if not token:
        return token
    f = _get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored broker token."""
    if not encrypted:
        return encrypted
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()
