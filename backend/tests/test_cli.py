"""
Tests for app/cli.py — the create-superuser command.

The CLI manages its own DB session via app.db.session.SessionLocal,
re-imported fresh inside the command on every invocation. To isolate each
test, we monkeypatch app.db.session.SessionLocal to point at a throwaway
on-disk SQLite database created per test.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from app.core.security import hash_password
from app.models.base import Base
from app.models.token import RefreshToken  # noqa: F401 — register table
from app.models.user import User, UserRole

runner = CliRunner()

STRONG_PASSWORD_1 = "Tr0ub4dor-correct-horse-1!"
STRONG_PASSWORD_2 = "Tr0ub4dor-correct-horse-2!"


@pytest.fixture()
def cli_db(tmp_path, monkeypatch):
    """
    Isolated on-disk SQLite DB for CLI tests.

    Yields a sessionmaker the test can call directly for setup/assertions.
    Monkeypatches app.db.session.SessionLocal so the CLI command (which does
    `from app.db.session import SessionLocal` fresh on every invocation)
    picks up this isolated database instead of the real one.
    """
    db_path = tmp_path / "cli_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )

    monkeypatch.setattr("app.db.session.SessionLocal", test_session_local)

    yield test_session_local

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _new_superuser_input(email: str, username: str, display_name: str, password: str) -> str:
    """Build the stdin sequence for the 'no existing superuser' prompts."""
    return f"{email}\n{username}\n{display_name}\n{password}\n{password}\n"


def _seed_superuser(cli_db, email: str, username: str, display_name: str) -> User:
    db = cli_db()
    user = User(
        email=email,
        username=username,
        display_name=display_name,
        hashed_password=hash_password(STRONG_PASSWORD_1),
        role=UserRole.superuser,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.close()
    return user


class TestCreateSuperuserNoExisting:
    def test_creates_successfully(self, cli_db) -> None:
        from app.cli import app as cli_app

        result = runner.invoke(
            cli_app,
            ["create-superuser"],
            input=_new_superuser_input(
                "first@example.com", "firstuser", "First User", STRONG_PASSWORD_1
            ),
        )
        assert result.exit_code == 0
        assert "Superuser created successfully" in result.stdout

        db = cli_db()
        user = db.query(User).filter(User.role == UserRole.superuser).first()
        assert user is not None
        assert user.email == "first@example.com"
        assert user.username == "firstuser"
        db.close()

    def test_does_not_prompt_for_replacement_when_none_exists(self, cli_db) -> None:
        """No existing superuser → straight to the creation prompts, no confirm dialogs."""
        from app.cli import app as cli_app

        result = runner.invoke(
            cli_app,
            ["create-superuser"],
            input=_new_superuser_input(
                "solo@example.com", "solouser", "Solo User", STRONG_PASSWORD_1
            ),
        )
        assert result.exit_code == 0
        assert "already exists" not in result.stdout


class TestCreateSuperuserExisting:
    def test_declines_first_prompt_makes_no_changes(self, cli_db) -> None:
        existing = _seed_superuser(cli_db, "existing@example.com", "existinguser", "Existing User")
        from app.cli import app as cli_app

        result = runner.invoke(cli_app, ["create-superuser"], input="n\n")
        assert result.exit_code == 0
        assert "No changes made" in result.stdout

        db = cli_db()
        users = db.query(User).filter(User.role == UserRole.superuser).all()
        assert len(users) == 1
        assert users[0].email == "existing@example.com"
        db.close()

    def test_confirms_first_declines_second_makes_no_changes(self, cli_db) -> None:
        """Two-step confirmation — declining the second prompt must also abort."""
        _seed_superuser(cli_db, "existing2@example.com", "existinguser2", "Existing User 2")
        from app.cli import app as cli_app

        result = runner.invoke(cli_app, ["create-superuser"], input="y\nn\n")
        assert result.exit_code == 0
        assert "No changes made" in result.stdout

        db = cli_db()
        users = db.query(User).filter(User.role == UserRole.superuser).all()
        assert len(users) == 1
        assert users[0].email == "existing2@example.com"
        db.close()

    def test_confirms_both_prompts_replaces_superuser(self, cli_db) -> None:
        _seed_superuser(cli_db, "old@example.com", "olduser", "Old User")
        from app.cli import app as cli_app

        result = runner.invoke(
            cli_app,
            ["create-superuser"],
            input="y\ny\n"
            + _new_superuser_input(
                "new@example.com", "newuser", "New User", STRONG_PASSWORD_2
            ),
        )
        assert result.exit_code == 0
        assert "Deleted existing superuser" in result.stdout
        assert "Superuser created successfully" in result.stdout

        db = cli_db()
        users = db.query(User).filter(User.role == UserRole.superuser).all()
        assert len(users) == 1
        assert users[0].email == "new@example.com"
        assert users[0].username == "newuser"
        db.close()

    def test_replacement_cascades_refresh_tokens(self, cli_db) -> None:
        """Deleting the old superuser must also remove their refresh tokens (FK cascade)."""
        from datetime import datetime, timedelta, timezone

        existing = _seed_superuser(cli_db, "tokens@example.com", "tokenuser", "Token User")

        db = cli_db()
        # Re-fetch in this session to get a usable ID
        existing = db.query(User).filter(User.email == "tokens@example.com").first()
        token = RefreshToken(
            jti_hash="a" * 64,
            user_id=existing.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(token)
        db.commit()
        db.close()

        from app.cli import app as cli_app

        result = runner.invoke(
            cli_app,
            ["create-superuser"],
            input="y\ny\n"
            + _new_superuser_input(
                "replacement@example.com", "replacementuser", "Replacement", STRONG_PASSWORD_2
            ),
        )
        assert result.exit_code == 0

        db = cli_db()
        remaining_tokens = db.query(RefreshToken).all()
        assert len(remaining_tokens) == 0
        db.close()
