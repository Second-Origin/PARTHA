"""Symmetric encryption for provider secrets stored at rest.

Provider API keys are the only secrets PARTHA persists on behalf of a user, and
they must never sit in the database in plaintext (E1.5 / #65). Fernet gives
authenticated symmetric encryption (AES-128-CBC + HMAC) with a single key read
from configuration — a KMS-managed key can be dropped in later behind the same
interface without touching call sites.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

__all__ = ["ProviderKeyCipher", "InvalidToken", "build_provider_cipher"]


class ProviderKeyCipher:
    """Encrypts and decrypts provider API keys with a configured Fernet key.

    The key comes from ``Settings.ai_encryption_key`` (env or KMS-injected). The
    ciphertext is a URL-safe token that carries its own IV and auth tag, so it is
    safe to store as an opaque string column.
    """

    def __init__(self, key: str) -> None:
        # A malformed key is a configuration error and must fail loudly at
        # startup rather than the first time a user saves a key.
        self._fernet = Fernet(key.encode("utf-8"))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        """Return the plaintext, or raise ``InvalidToken`` if the ciphertext was
        produced with a different key or tampered with."""
        return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")


def build_provider_cipher(settings: Settings) -> ProviderKeyCipher:
    return ProviderKeyCipher(settings.ai_encryption_key)
