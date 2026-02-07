"""
Encrypted JSON Column Type

Transparent Fernet encryption for SQLAlchemy JSON columns.
Secrets are encrypted at rest in the database and decrypted
on read — consumers always see a plain Python dict.

Key Derivation:
    Uses SHA-256 of SECRET_KEY to produce a Fernet-compatible
    32-byte key (base64-encoded). Same SECRET_KEY used for JWT
    signing — single source of truth.

Legacy Handling:
    If a stored value fails to decrypt (i.e., it was written as
    plaintext JSON before encryption was enabled), the type falls
    back to parsing it as raw JSON and logs a warning. The value
    will be encrypted on next write.
"""
import base64
import hashlib
import json
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text, TypeDecorator

from .logging_config import get_logger

logger = get_logger(__name__)

_fernet_cache: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    """Get or create Fernet instance from SECRET_KEY."""
    global _fernet_cache
    if _fernet_cache is None:
        secret = os.getenv("SECRET_KEY", "coalmine-dev-secret-change-in-production")
        # Derive a 32-byte key from SECRET_KEY via SHA-256
        key_bytes = hashlib.sha256(secret.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        _fernet_cache = Fernet(fernet_key)
    return _fernet_cache


class EncryptedJSON(TypeDecorator):
    """
    SQLAlchemy column type that stores JSON data encrypted at rest.

    On write:  dict → JSON string → Fernet.encrypt() → stored as Text
    On read:   stored Text → Fernet.decrypt() → JSON parse → dict

    Falls back to raw JSON parsing for legacy plaintext values.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypt dict → ciphertext string for storage."""
        if value is None:
            return None
        plaintext = json.dumps(value)
        return _get_fernet().encrypt(plaintext.encode()).decode("utf-8")

    def process_result_value(self, value, dialect):
        """Decrypt stored ciphertext → dict for application use."""
        if value is None:
            return None
        try:
            decrypted = _get_fernet().decrypt(value.encode())
            return json.loads(decrypted)
        except InvalidToken:
            # Legacy plaintext JSON — decrypt failed, try raw parse
            try:
                result = json.loads(value)
                logger.warning(
                    "Read unencrypted secrets from DB — will encrypt on next write"
                )
                return result
            except (json.JSONDecodeError, TypeError):
                logger.error("Failed to decrypt or parse secrets column")
                return None
