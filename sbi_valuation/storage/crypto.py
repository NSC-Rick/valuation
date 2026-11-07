"""
Passphrase-based encryption for assessment export files.

V1 persistence model (per approved decision): the application keeps NO
server-side storage. "Save" produces a download encrypted with a key
derived from the user's passphrase; "Resume" uploads and decrypts it.
Data at rest therefore exists only as files the user holds — nothing to
leak from the service, nothing shared between users.

Key derivation: PBKDF2-HMAC-SHA256, 480k iterations, 16-byte random salt.
Encryption: Fernet (AES-128-CBC + HMAC-SHA256).
"""
from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

KDF_ITERATIONS = 480_000
SALT_BYTES = 16


class DecryptionError(ValueError):
    """Raised when decryption fails (wrong passphrase or corrupted file)."""


def derive_key(passphrase: str, salt: bytes, iterations: int = KDF_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt(plaintext: bytes, passphrase: str) -> dict:
    """Encrypt bytes; returns {"salt","iterations","ciphertext"} dict."""
    salt = os.urandom(SALT_BYTES)
    f = Fernet(derive_key(passphrase, salt))
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "iterations": KDF_ITERATIONS,
        "ciphertext": f.encrypt(plaintext).decode("ascii"),
    }


def decrypt(blob: dict, passphrase: str) -> bytes:
    """Decrypt an encrypt() result; raises DecryptionError on failure."""
    try:
        salt = base64.b64decode(blob["salt"])
        iterations = int(blob.get("iterations", KDF_ITERATIONS))
        f = Fernet(derive_key(passphrase, salt, iterations))
        return f.decrypt(blob["ciphertext"].encode("ascii"))
    except (InvalidToken, KeyError, ValueError, TypeError) as exc:
        raise DecryptionError(
            "Could not decrypt this file — the passphrase may be incorrect "
            "or the file may be corrupted or not an assessment export."
        ) from exc
