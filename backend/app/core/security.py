import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import httpx
from jose import jwt
from zxcvbn import zxcvbn

from app.core.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing
#
# Using bcrypt directly rather than via passlib: passlib's bcrypt backend
# detection breaks on bcrypt >= 4.1 (removed __about__) and >= 4.0
# (stricter 72-byte enforcement in the wrap-bug probe).
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a password with bcrypt. Returns a utf-8 decoded hash string."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison of plain-text against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# Password validation
#
# Two-stage check:
#   1. Synchronous: length gate (12–128 chars) + zxcvbn strength (score >= 3)
#   2. Async:       HIBP k-anonymity API (only when CHECK_PWNED_PASSWORDS=True)
#
# Callers should call validate_password_strength() first, then
# await check_pwned_password() if they want the breach check.
# The combined helper await validate_password() does both in sequence.
# ---------------------------------------------------------------------------

_MIN_LENGTH = 12
_MAX_LENGTH = 128
_MIN_ZXCVBN_SCORE = 3

_ZXCVBN_FEEDBACK = {
    0: "This password is extremely weak",
    1: "This password is very weak",
    2: "This password is too weak — try adding length, mixed case, numbers, or symbols",
}


def validate_password_strength(password: str) -> None:
    """
    Synchronous checks: length gate + zxcvbn score.

    Raises HTTPException 422 if the password fails either check.
    Safe to call from sync or async contexts.
    """
    from fastapi import HTTPException, status

    if len(password) < _MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Password must be at least {_MIN_LENGTH} characters",
        )
    if len(password) > _MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Password must be at most {_MAX_LENGTH} characters",
        )

    result = zxcvbn(password)
    score = result["score"]  # 0–4; we require >= 3
    if score < _MIN_ZXCVBN_SCORE:
        feedback = result.get("feedback", {})
        suggestions = feedback.get("suggestions", [])
        warning = feedback.get("warning", "")

        # Build a useful message without exposing the raw score.
        message = _ZXCVBN_FEEDBACK.get(score, "Password is not strong enough")
        if warning:
            message = f"{message}. {warning}"
        if suggestions:
            message = f"{message}. {suggestions[0]}"

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=message,
        )


async def check_pwned_password(password: str) -> None:
    """
    Async HIBP k-anonymity check.

    Only runs when settings.CHECK_PWNED_PASSWORDS is True.
    Uses the range API — only the first 5 hex chars of SHA1(password) are
    ever sent to the remote server, preserving full privacy.

    Raises HTTPException 422 if the password appears in a known breach.
    Network errors are logged and silently ignored (fail open) to avoid
    blocking legitimate users due to transient HIBP outages.
    """
    if not settings.CHECK_PWNED_PASSWORDS:
        return

    from fastapi import HTTPException, status
    import logging
    logger = logging.getLogger(__name__)

    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"Add-Padding": "true"},  # prevents traffic analysis
            )
            resp.raise_for_status()
    except Exception as exc:
        # Fail open: a network hiccup should not prevent password changes.
        logger.warning("HIBP check failed (ignoring): %s", exc)
        return

    # Response is lines of "HASH_SUFFIX:COUNT"
    for line in resp.text.splitlines():
        parts = line.split(":")
        if len(parts) != 2:
            continue
        found_suffix, count_str = parts
        if found_suffix.upper() == suffix:
            try:
                count = int(count_str.strip())
            except ValueError:
                count = 1
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"This password has appeared in {count:,} known data breaches "
                    "and cannot be used. Please choose a different password."
                ),
            )


async def validate_password(password: str) -> None:
    """
    Combined password validation: strength check then breach check.

    Call this from any async context (service methods) before hashing.
    The sync strength check always runs; the breach check is gated by
    settings.CHECK_PWNED_PASSWORDS.
    """
    validate_password_strength(password)
    await check_pwned_password(password)


# ---------------------------------------------------------------------------
# JTI (JWT ID) utilities
# ---------------------------------------------------------------------------

def generate_jti() -> str:
    """Generate a cryptographically random JWT ID."""
    return str(uuid.uuid4())


def hash_jti(jti: str) -> str:
    """
    SHA-256 hash a JTI before storing in the database.

    The JTI is the credential that grants a refresh. Hashing it means a raw
    DB dump cannot be replayed without also knowing the SECRET_KEY.
    """
    return hashlib.sha256(jti.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(subject: str) -> str:
    """
    Short-lived access token. NOT stored in the database.

    Claims: sub (user_id), jti, type="access", iat, exp
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": generate_jti(),
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """
    Longer-lived refresh token. Caller stores hash_jti(jti) in the database.

    Returns: (encoded_token, jti, expires_at)
    """
    jti = generate_jti()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }
    encoded = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded, jti, expire


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------

def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT.
    Raises jose.JWTError on invalid signature, expiry, or malformed token.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
