from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.token import RefreshToken


class TokenRepository:
    """
    Data-access layer for the ``refresh_tokens`` whitelist table.

    Rules:
    - No business logic.
    - Returns ORM model instances.
    - Uses flush() — the service layer commits.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_by_jti_hash(self, jti_hash: str) -> Optional[RefreshToken]:
        """Look up a token by its stored SHA-256(jti)."""
        stmt = select(RefreshToken).where(RefreshToken.jti_hash == jti_hash)
        return self._db.scalar(stmt)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create(self, token: RefreshToken) -> RefreshToken:
        self._db.add(token)
        self._db.flush()
        self._db.refresh(token)
        return token

    def revoke(self, token: RefreshToken) -> RefreshToken:
        """Mark a single token as revoked."""
        token.revoked = True
        self._db.flush()
        return token

    def revoke_all_for_user(self, user_id: str) -> int:
        """
        Revoke all non-revoked tokens for a user.
        Useful for forced logout / security events.
        Returns the number of tokens revoked.
        """
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
        tokens = list(self._db.scalars(stmt).all())
        for token in tokens:
            token.revoked = True
        self._db.flush()
        return len(tokens)

    def delete_expired(self) -> int:
        """
        Hard-delete all expired tokens (revoked or not).
        Called at startup and can be triggered periodically.
        Returns the number of rows deleted.
        """
        now = datetime.now(timezone.utc)
        stmt = delete(RefreshToken).where(RefreshToken.expires_at < now)
        result = self._db.execute(stmt)
        self._db.flush()
        return result.rowcount
