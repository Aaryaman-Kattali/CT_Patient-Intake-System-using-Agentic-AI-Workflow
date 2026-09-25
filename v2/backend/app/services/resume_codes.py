"""Stable, readable resume codes (e.g. K7P-4MX).

The code is derived from APP_SECRET and the intake id, so it is the same at every pause and
never has to be stored. The database keeps only a scrypt hash, used to find the intake.
Phase 6 must rate-limit failed resume attempts per code and per client.
"""

import hashlib
import hmac
from uuid import UUID

# No look-alikes: no 0/O, 1/I/L, and no U (U/V).
ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
LENGTH = 6
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def resume_code_for(intake_id: UUID, secret: bytes) -> str:
    digest = hmac.new(secret, b"resume-code:" + intake_id.bytes, hashlib.sha256).digest()
    number = int.from_bytes(digest, "big")
    chars = []
    for _ in range(LENGTH):
        number, index = divmod(number, len(ALPHABET))
        chars.append(ALPHABET[index])
    code = "".join(chars)
    return f"{code[:3]}-{code[3:]}"


def normalize(code: str) -> str | None:
    """Accept any case, spaces or dashes. None if it cannot be a valid code."""
    cleaned = "".join(ch for ch in code.upper() if ch.isalnum())
    if len(cleaned) != LENGTH or any(ch not in ALPHABET for ch in cleaned):
        return None
    return cleaned


def lookup_hash(code: str, secret: bytes) -> str | None:
    cleaned = normalize(code)
    if cleaned is None:
        return None
    salt = hmac.new(secret, b"resume-code-salt", hashlib.sha256).digest()
    return hashlib.scrypt(cleaned.encode(), salt=salt, **_SCRYPT).hex()
