"""
Shared pytest fixtures.

Test strategy:
- Each test session spins up a fresh in-memory SQLite DB.
- All tables are created via SQLAlchemy metadata (no Alembic in tests).
- The `get_db` dependency is overridden so every test client uses the
  test session, not the application session.
- Fixtures are function-scoped by default so each test starts clean.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base
from app.models.token import RefreshToken  # noqa: F401
from app.models.project import Project, ProjectMember  # noqa: F401
from app.models.category import Category  # noqa: F401 — ensure table is registered
from app.models.bitza import Bitza, BitzaImage, BitzaKind, Checkout, StockLog  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.system_config import SystemConfig  # noqa: F401
from app.core.security import hash_password

# ---------------------------------------------------------------------------
# In-memory test engine (shared connection so tables persist across sessions).
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # single shared connection — required for :memory: DBs
)


@event.listens_for(test_engine, "connect")
def _configure_test_sqlite(dbapi_conn, _record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


TestSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Create schema once per session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# ---------------------------------------------------------------------------
# Per-test DB session (function-scoped — rolls back after each test).
# ---------------------------------------------------------------------------

@pytest.fixture()
def db() -> Session:
    """
    Yields a transactional test session.
    Everything done in the test is rolled back at the end, keeping tests
    independent without recreating tables each time.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ---------------------------------------------------------------------------
# Override get_db to use the test session.
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db: Session) -> TestClient:
    """
    TestClient whose requests use the test DB session.
    """

    def _override_get_db():
        try:
            yield db
        finally:
            pass  # cleanup handled by the `db` fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pre-built user fixtures — unchanged from Phase 1/2
# ---------------------------------------------------------------------------

@pytest.fixture()
def superuser(db: Session) -> User:
    user = User(
        email="super@example.com",
        username="superuser",
        display_name="Super User",
        hashed_password=hash_password("Sup3r-C0rrect-Horse!"),
        role=UserRole.superuser,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def admin_user(db: Session) -> User:
    user = User(
        email="admin@example.com",
        username="adminuser",
        display_name="Admin User",
        hashed_password=hash_password("Adm1n-C0rrect-Horse!"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def normal_user(db: Session) -> User:
    user = User(
        email="user@example.com",
        username="normaluser",
        display_name="Normal User",
        hashed_password=hash_password("Us3r-C0rrect-Horse!!"),
        role=UserRole.user,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def second_user(db: Session) -> User:
    """A second normal user — needed for tests that require two distinct
    holders/members (project membership, checkout-to-another-user cases)."""
    user = User(
        email="second@example.com",
        username="seconduser",
        display_name="Second User",
        hashed_password=hash_password("S3cond-C0rrect-Horse!"),
        role=UserRole.user,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def suspended_user(db: Session) -> User:
    user = User(
        email="suspended@example.com",
        username="suspendeduser",
        display_name="Suspended User",
        hashed_password=hash_password("Us3r-C0rrect-Horse!!"),
        role=UserRole.user,
        is_active=False,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Auth token helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def superuser_token(client: TestClient, superuser: User) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "superuser", "password": "Sup3r-C0rrect-Horse!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin_token(client: TestClient, admin_user: User) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin@example.com", "password": "Adm1n-C0rrect-Horse!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def user_token(client: TestClient, normal_user: User) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def second_user_token(client: TestClient, second_user: User) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "seconduser", "password": "S3cond-C0rrect-Horse!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# A default project — most bitza tests need one to satisfy the mandatory
# responsible_project_id field, so it's provided as a fixture rather than
# re-created in every test module.
# ---------------------------------------------------------------------------

@pytest.fixture()
def default_project(db: Session) -> Project:
    project = Project(name="Workshop", description="Default test project")
    db.add(project)
    db.flush()
    return project


@pytest.fixture(autouse=True)
def root_bitza(db: Session, default_project: Project) -> Bitza:
    """
    Every test gets a root bitza automatically. Ordinary bitza creation
    now always requires a parent — the root is meant to be created
    exactly once, via the CLI's create-root command, never through the
    ordinary POST /bitzas/ endpoint (see BitzaCreate.parent_id,
    BitzaService.create_root_bitza). Built directly via ORM, bypassing
    create_root_bitza, matching how default_project above bypasses its own
    service layer — there's no HTTP path that could create this for us
    anyway. Autouse + conftest-level (rather than local to
    test_bitzas.py) because test_projects.py also creates bitzas via the API
    and needs one to exist too; harmless for test files that don't touch
    bitzas at all (test_cli.py manages its own isolated DB entirely and
    never requests this fixture; no other file asserts an exact global
    count of bitzas/projects that an extra row here would upset).
    """
    root = Bitza(
        name="Test Root",
        kind=BitzaKind.fixed,
        parent_id=None,
        responsible_project_id=default_project.id,
    )
    db.add(root)
    db.flush()
    db.add(SystemConfig(root_bitza_id=root.id))
    db.flush()
    return root
