"""Authenticated encryption helpers for server-side OIDC sessions.

Tokens are encrypted at rest with AES-256-GCM. The browser receives only a
random opaque session cookie; no OIDC token is ever exposed by this module.
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings

_AAD_PREFIX = b"dikevia:oidc-session:v1:"


def decode_encryption_key(value: str) -> bytes:
    """Accept a 32-byte hex or URL-safe base64 key; reject all other lengths."""
    if not isinstance(value, str) or not value:
        raise ValueError("Missing encryption key")
    raw = None
    if len(value) == 64:
        try:
            raw = bytes.fromhex(value)
        except ValueError:
            raw = None
    if raw is None:
        try:
            raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except Exception as exc:
            raise ValueError("Invalid encryption key encoding") from exc
    if len(raw) != 32:
        raise ValueError("Encryption key must be exactly 32 bytes")
    return raw


def _cipher() -> AESGCM:
    return AESGCM(decode_encryption_key(settings.oidc_session_encryption_key))


def encrypt_session_value(value: str, purpose: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("Session value cannot be empty")
    if purpose not in {"access", "identity", "refresh", "login-flow"}:
        raise ValueError("Unsupported session encryption purpose")
    nonce = os.urandom(12)
    ciphertext = _cipher().encrypt(nonce, value.encode("utf-8"), _AAD_PREFIX + purpose.encode("ascii"))
    return nonce + ciphertext


def decrypt_session_value(payload: bytes, purpose: str) -> str:
    if not isinstance(payload, (bytes, bytearray)) or len(payload) < 29:
        raise ValueError("Invalid encrypted session value")
    if purpose not in {"access", "identity", "refresh", "login-flow"}:
        raise ValueError("Unsupported session encryption purpose")
    plaintext = _cipher().decrypt(bytes(payload[:12]), bytes(payload[12:]), _AAD_PREFIX + purpose.encode("ascii"))
    return plaintext.decode("utf-8")


def hash_session_cookie(cookie_value: str) -> str:
    if not isinstance(cookie_value, str) or len(cookie_value) < 40 or len(cookie_value) > 128:
        raise ValueError("Invalid session cookie")
    return hashlib.sha256(cookie_value.encode("ascii")).hexdigest()
