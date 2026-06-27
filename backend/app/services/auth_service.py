from datetime import datetime, timezone

from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    RevokedTokenError,
    UserSuspendedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_jti,
    verify_password,
)
from app.models.token import RefreshToken
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse


class AuthService:
    """
    All authentication and token-lifecycle logic lives here.

    Responsibilities:
    - Credential validation
    - JWT issuance (access + refresh)
    - Refresh with token rotation
    - Logout (revocation)
    - Access-token validation for request authentication
    - Expired-token cleanup

    No ORM queries are performed directly — delegated to repositories.
    Transactions are committed here; repositories only flush.
    """

    def __init__(
        self,
        db: Session,
        user_repo: UserRepository,
        token_repo: TokenRepository,
    ) -> None:
        self._db = db
        self._user_repo = user_repo
        self._token_repo = token_repo

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, identifier: str, password: str) -> TokenResponse:
        """
        Authenticate by email-or-username + password.

        On success: issues an access token + refresh token; stores the
        hashed refresh JTI in the DB.
        """
        user = self._user_repo.get_by_identifier(identifier)

        # Deliberate: same error for "not found" and "wrong password" to
        # prevent user-enumeration via timing or error differentiation.
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise UserSuspendedError()

        access_token = create_access_token(subject=user.id)
        refresh_token_str, jti, expires_at = create_refresh_token(subject=user.id)

        db_token = RefreshToken(
            jti_hash=hash_jti(jti),
            user_id=user.id,
            expires_at=expires_at,
        )
        self._token_repo.create(db_token)
        self._db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
        )

    # ------------------------------------------------------------------
    # Refresh with rotation
    # ------------------------------------------------------------------

    def refresh(self, refresh_token: str) -> TokenResponse:
        """
        Validate a refresh token, revoke it, and issue a fresh pair.

        Rotation: the old token is revoked immediately; a new refresh token
        is stored.  Attempting to reuse the old token returns 401.
        """
        # 1. Validate JWT signature and expiry.
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise InvalidTokenError("Invalid or expired refresh token")

        # 2. Enforce token type — reject access tokens used as refresh tokens.
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Token type mismatch — refresh token required")

        jti: str | None = payload.get("jti")
        user_id: str | None = payload.get("sub")
        if not jti or not user_id:
            raise InvalidTokenError("Malformed token payload")

        # 3. Check DB whitelist.
        db_token = self._token_repo.get_by_jti_hash(hash_jti(jti))
        if not db_token:
            raise InvalidTokenError("Token not recognised")

        if db_token.revoked:
            # A revoked token being presented may indicate token theft.
            raise RevokedTokenError()

        # Belt-and-braces expiry check (JWT decode already validates exp,
        # but DB expiry is the authoritative source after any clock skew).
        # UTCDateTime ensures db_token.expires_at is always timezone-aware.
        if db_token.expires_at < datetime.now(timezone.utc):
            raise InvalidTokenError("Refresh token has expired")

        # 4. Ensure the user is still active.
        user = self._user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UserSuspendedError()

        # 5. Rotate: revoke old, issue new pair.
        self._token_repo.revoke(db_token)

        new_access = create_access_token(subject=user.id)
        new_refresh_str, new_jti, new_expires = create_refresh_token(subject=user.id)

        new_db_token = RefreshToken(
            jti_hash=hash_jti(new_jti),
            user_id=user.id,
            expires_at=new_expires,
        )
        self._token_repo.create(new_db_token)
        self._db.commit()

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh_str,
        )

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def logout(self, refresh_token: str) -> None:
        """
        Revoke the supplied refresh token.

        Silently succeeds if the token is already revoked or not found
        (idempotent logout).
        """
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise InvalidTokenError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Token type mismatch — refresh token required")

        jti: str | None = payload.get("jti")
        if not jti:
            raise InvalidTokenError("Malformed token payload")

        db_token = self._token_repo.get_by_jti_hash(hash_jti(jti))
        if db_token and not db_token.revoked:
            self._token_repo.revoke(db_token)
            self._db.commit()

    # ------------------------------------------------------------------
    # Access-token validation (called on every authenticated request)
    # ------------------------------------------------------------------

    def get_current_user_id_from_access_token(self, token: str) -> str:
        """
        Validate an access token (signature + expiry + type).
        No DB lookup — stateless by design.

        Returns the user_id (sub claim) on success.
        """
        try:
            payload = decode_token(token)
        except JWTError:
            raise InvalidTokenError()

        # Hard-reject refresh tokens presented as access tokens.
        if payload.get("type") != "access":
            raise InvalidTokenError("Token type mismatch — access token required")

        user_id: str | None = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Malformed token payload")

        return user_id

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def cleanup_expired_tokens(self) -> int:
        """Delete expired refresh tokens. Returns count deleted."""
        count = self._token_repo.delete_expired()
        self._db.commit()
        return count
