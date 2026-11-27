import os

from cryptography.fernet import Fernet

from shared.infrastructure.google.drive_client import NotConfigured


def _fernet() -> Fernet:
    """Build the cipher from the configured encryption key."""
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise NotConfigured("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(key)


def encrypt(value: str) -> str:
    """Encrypt a text value."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a text value."""
    return _fernet().decrypt(value.encode()).decode()
