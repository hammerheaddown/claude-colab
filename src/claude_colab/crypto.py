"""Fernet E2E encryption for claude-colab.

All request/response bodies (except /health) are encrypted with a per-session
Fernet key. Cloudflare sees only ciphertext.
"""

import json

from cryptography.fernet import Fernet


def generate_key() -> bytes:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key()


def encrypt(key: bytes, data: dict) -> bytes:
    """Encrypt a JSON-serializable dict to ciphertext bytes."""
    f = Fernet(key)
    plaintext = json.dumps(data).encode("utf-8")
    return f.encrypt(plaintext)


def decrypt(key: bytes, ciphertext: bytes) -> dict:
    """Decrypt ciphertext bytes back to a dict."""
    f = Fernet(key)
    plaintext = f.decrypt(ciphertext)
    return json.loads(plaintext.decode("utf-8"))
