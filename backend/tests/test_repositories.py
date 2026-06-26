"""
Unit tests for UserRepository and TokenRepository.

These tests hit the DB directly (no HTTP), verifying that the repository
layer correctly reads and writes models without business logic.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_jti
from app.models.token import RefreshToken
from app.models.user import User, UserRole
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    email: str = "repo@example.com",
    username: str = "repouser",
    role: UserRole = UserRole.user,
    is_active: bool = True,
) -> User:
    return User(
        email=email,
        username=username,
        display_name="Repo User",
        hashed_password=hash_password("SomePass1!"),
        role=role,
        is_active=is_active,
    )


def _make_token(user_id: str, days: int = 30, revoked: bool = False) -> RefreshToken:
    jti = str(uuid.uuid4())
    return RefreshToken(
        jti_hash=hash_jti(jti),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
        revoked=revoked,
    )


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------

class TestUserRepository:
    def test_create_and_get_by_id(self, db: Session) -> None:
        repo = UserRepository(db)
        user = _make_user()
        created = repo.create(user)
        db.commit()

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.email == "repo@example.com"

    def test_get_by_email(self, db: Session) -> None:
        repo = UserRepository(db)
        repo.create(_make_user(email="a@test.com", username="a"))
        db.commit()

        assert repo.get_by_email("a@test.com") is not None
        assert repo.get_by_email("missing@test.com") is None

    def test_get_by_username(self, db: Session) -> None:
        repo = UserRepository(db)
        repo.create(_make_user(email="b@test.com", username="buser"))
        db.commit()

        assert repo.get_by_username("buser") is not None
        assert repo.get_by_username("ghost") is None

    def test_get_by_identifier_email(self, db: Session) -> None:
        repo = UserRepository(db)
        repo.create(_make_user(email="c@test.com", username="cuser"))
        db.commit()

        assert repo.get_by_identifier("c@test.com") is not None

    def test_get_by_identifier_username(self, db: Session) -> None:
        repo = UserRepository(db)
        repo.create(_make_user(email="d@test.com", username="duser"))
        db.commit()

        assert repo.get_by_identifier("duser") is not None

    def test_get_superuser_returns_none_when_absent(self, db: Session) -> None:
        repo = UserRepository(db)
        assert repo.get_superuser() is None

    def test_get_superuser(self, db: Session) -> None:
        repo = UserRepository(db)
        repo.create(_make_user(email="su@test.com", username="su", role=UserRole.superuser))
        db.commit()

        su = repo.get_superuser()
        assert su is not None
        assert su.role == UserRole.superuser

    def test_list_users_with_role_filter(self, db: Session) -> None:
        repo = UserRepository(db)
        repo.create(_make_user(email="u1@test.com", username="u1", role=UserRole.user))
        repo.create(_make_user(email="u2@test.com", username="u2", role=UserRole.admin))
        db.commit()

        users = repo.list_users(role=UserRole.user)
        assert all(u.role == UserRole.user for u in users)

    def test_delete_user(self, db: Session) -> None:
        repo = UserRepository(db)
        user = repo.create(_make_user(email="del@test.com", username="del"))
        db.commit()

        repo.delete(user)
        db.commit()

        assert repo.get_by_id(user.id) is None

    def test_update_user(self, db: Session) -> None:
        repo = UserRepository(db)
        user = repo.create(_make_user(email="upd@test.com", username="upd"))
        db.commit()

        user.display_name = "Changed"
        updated = repo.update(user)
        db.commit()

        assert updated.display_name == "Changed"


# ---------------------------------------------------------------------------
# TokenRepository
# ---------------------------------------------------------------------------

class TestTokenRepository:
    def _persisted_user(self, db: Session) -> User:
        repo = UserRepository(db)
        user = _make_user(
            email=f"tok{uuid.uuid4().hex[:6]}@test.com",
            username=f"tok{uuid.uuid4().hex[:6]}",
        )
        created = repo.create(user)
        db.commit()
        return created

    def test_create_and_get_by_jti_hash(self, db: Session) -> None:
        user = self._persisted_user(db)
        repo = TokenRepository(db)

        jti = str(uuid.uuid4())
        jti_hash = hash_jti(jti)
        token = RefreshToken(
            jti_hash=jti_hash,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        repo.create(token)
        db.commit()

        found = repo.get_by_jti_hash(jti_hash)
        assert found is not None
        assert found.revoked is False

    def test_revoke_token(self, db: Session) -> None:
        user = self._persisted_user(db)
        repo = TokenRepository(db)
        token = _make_token(user.id)
        repo.create(token)
        db.commit()

        repo.revoke(token)
        db.commit()

        found = repo.get_by_jti_hash(token.jti_hash)
        assert found is not None
        assert found.revoked is True

    def test_revoke_all_for_user(self, db: Session) -> None:
        user = self._persisted_user(db)
        repo = TokenRepository(db)
        for _ in range(3):
            repo.create(_make_token(user.id))
        db.commit()

        count = repo.revoke_all_for_user(user.id)
        db.commit()

        assert count == 3

    def test_delete_expired(self, db: Session) -> None:
        user = self._persisted_user(db)
        repo = TokenRepository(db)

        # One already-expired token
        expired = RefreshToken(
            jti_hash=hash_jti(str(uuid.uuid4())),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        # One still-valid token
        valid = _make_token(user.id, days=7)

        repo.create(expired)
        repo.create(valid)
        db.commit()

        deleted = repo.delete_expired()
        db.commit()

        assert deleted >= 1
        assert repo.get_by_jti_hash(valid.jti_hash) is not None
        assert repo.get_by_jti_hash(expired.jti_hash) is None
