# FastAPI CRUD API — Project Context Instructions

General-purpose system instructions for building production-disciplined CRUD
APIs using FastAPI, SQLAlchemy (sync), SQLite, and uv. These instructions apply
to any domain — user management, asset tracking, inventory, content management,
etc. Auth and JWT sections apply only when authentication is required.

---

## 1. Core Technology Stack (MANDATORY)

- Python 3.11+ managed by **uv** (see Section 11)
- FastAPI (latest stable)
- SQLAlchemy 2.x — **synchronous only**
- Pydantic v2
- SQLite — no external database (with spaitalite extension when required for spatial data)
- Alembic for migrations
- pytest for testing
- JWT: `python-jose` + `bcrypt` (when auth is required)
- `zxcvbn` for password checking (when auth is required)

**DO NOT:**
- Use async DB access
- Use SQLModel
- Use external services (Redis, queues, etc.)
- Use `passlib` — use `bcrypt` directly instead (passlib breaks on bcrypt >= 4.1)

---

## 2. Architecture (STRICTLY ENFORCED)

```
API (routes / controllers)
    ↓
Services (business logic)
    ↓
Repositories (data access only)
    ↓
DB (engine + session only)
```

### Layer rules

**API layer:**
- No business logic
- No ORM imports
- Thin: validate input, call service, return response model

**Services:**
- No ORM queries — delegate entirely to repositories
- Own all business logic, permission checks, and transaction commits
- Enrich response objects with denormalised display fields via `_enrich_*` private methods

**Repositories:**
- No business logic
- DB interaction only: reads, writes, deletes
- Use `flush()` not `commit()` — the service layer owns transaction boundaries
- Return ORM model instances

**DB layer:**
- Session and engine management only

---

## 3. Required Project Structure

```
app/
  main.py                    # App factory, lifespan, CORS, exception handlers

  api/
    v1/
      router.py              # Aggregates all endpoint routers
      endpoints/
        auth.py              # (if auth required)
        <domain>.py          # One file per resource domain

  services/
    auth_service.py          # (if auth required)
    <domain>_service.py

  repositories/
    <domain>_repository.py
    token_repository.py      # (if auth required)

  models/
    base.py                  # DeclarativeBase + UTCDateTime TypeDecorator
    <domain>.py

  schemas/
    auth.py                  # (if auth required)
    <domain>.py

  db/
    session.py               # Engine, pragmas, get_db dependency

  core/
    config.py                # Pydantic BaseSettings
    security.py              # bcrypt, JWT utils (if auth required)
    exceptions.py            # Custom HTTPException subclasses
    dependencies.py          # All FastAPI DI providers

alembic/
  env.py
  versions/

tests/
data/                        # SQLite DB files (gitignored)
pyproject.toml
.python-version
uv.lock
```

---

## 4. Database Configuration (SQLite)

### Engine setup

```python
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
```

### Per-connection PRAGMAs (MANDATORY)

```python
@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")   # concurrent readers
    cursor.execute("PRAGMA foreign_keys=ON;")    # FK enforcement (off by default)
    cursor.close()
```

### Session factory

```python
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # REQUIRED: ORM objects must remain usable after
                               # commit without triggering lazy loads, because
                               # the session may close before response serialisation.
)
```

### Datetime handling — UTCDateTime TypeDecorator (MANDATORY)

SQLite has no native datetime type. It strips timezone info on read-back, even
when columns are declared `DateTime(timezone=True)`. **Never** use
`DateTime(timezone=True)` directly. Always use the `UTCDateTime` TypeDecorator
defined in `app/models/base.py`:

```python
class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)  # treat naive as UTC
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)  # re-attach on read
        return value
```

Rules:
- Use `UTCDateTime` for **every** datetime column in every model
- Always write with `datetime.now(timezone.utc)` — never `datetime.utcnow()`
- Never use `synchronize_session=False` as a workaround for naive/aware
  comparison errors — fix the root cause with `UTCDateTime`
- Pydantic v2 serialises timezone-aware datetimes with a `Z` suffix
  automatically — no extra config needed

### JSON / array columns

SQLite has no native array type. Use `JSON` for list fields (e.g. tags):

```python
tags: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
```

---

## 5. Schema Design (Pydantic v2)

Define **separate** schemas for each purpose:

- `<Resource>Create` — write schema for creation
- `<Resource>Update` — write schema for partial updates (all fields `Optional`)
- `<Resource>Read` — full read schema returned from API
- `<Resource>ListRead` — compact read schema for list endpoints

Rules:
- **Never** expose ORM models directly from endpoints
- Always use `model_config = ConfigDict(from_attributes=True)` on read schemas
- Add display-name and computed fields (e.g. `owner_display_name`, `item_count`)
  with default values of `""` or `0` — populate them in the service `_enrich_*` methods
- Validate and normalise on input (e.g. lowercase email/username, strip whitespace)

---

## 6. Authentication — JWT Hybrid (when required)

### Token types

**Access token** — short-lived (15 min default), NOT stored in DB.
Claims: `sub` (user_id), `exp`, `jti`, `type = "access"`, `iat`

**Refresh token** — long-lived (30 days default), MUST be stored in DB as a
whitelist. Store `SHA256(jti)` — never the raw token or JTI.
Claims: `sub`, `exp`, `jti`, `type = "refresh"`, `iat`

### Refresh token table

```
id, jti_hash (unique, indexed), user_id (FK), expires_at, revoked (bool), created_at
```

### Auth flow

**Login:** validate credentials → issue access + refresh → store `hash_jti(jti)` in DB

**Refresh:** validate JWT → check DB (exists, not revoked, not expired) →
revoke old token → issue new pair (rotation)

**Logout:** revoke refresh token in DB (idempotent)

**Authenticated request:** validate access token signature + type — no DB lookup

### Password policy

- Password strength must be evaluated using zxcvbn.
- A password is only acceptable if it achieves a zxcvbn score of 3 or higher.
- Passwords must have a minimum length of 12 and maximum length of 128 chars.
- Password composition rules (uppercase, digits, symbols) must not be used as the primary strength mechanism.
- Passwords must also be checked against known breached password datasets unless the app is expected to be run on a non public facing network.
- Frontend and backend must use zxcvbn to ensure consistent strength evaluation.
- Backend validation is authoritative; frontend validation is advisory only.

### Security rules

- Include `jti` in all tokens
- Enforce `type` claim — reject refresh tokens used as access tokens and vice versa
- Hash JTIs with `SHA256` before DB storage
- Superuser: cannot be suspended; created via CLI only, never via API
- Implement expired-token cleanup on startup and/or periodically

---

## 7. Repository Layer Rules

- Accept a `Session` in `__init__`
- Return ORM model instances
- Use `flush()` — never `commit()`
- No business logic, no permission checks
- No raw SQL strings outside repository methods (use SQLAlchemy constructs)

---

## 8. Service Layer Rules

- No direct ORM queries — use repositories only
- Own all `commit()` calls — repositories only flush
- Enforce all business rules and permission checks
- Use private `_enrich_*` methods to add denormalised/computed fields to read schemas
- Use private `_can_*` methods to encapsulate permission logic
- Raise custom `HTTPException` subclasses (from `app/core/exceptions.py`)
- Write audit log entries for significant mutations if an audit log is in scope

---

## 9. API Layer Rules

- No business logic — call service, return result
- Use `response_model` on every endpoint
- Use `Depends()` for all dependencies — never instantiate services or repos directly
- Document status codes with `responses={}` on non-obvious endpoints
- Use appropriate HTTP status codes:
  - `201` for creation
  - `204` for delete / logout (no body)
  - `404` for not-found (including privacy-masked resources)
  - `409` for uniqueness conflicts or blocked deletes

---

## 10. Dependency Injection

Provide a provider function for every repository and service:

```python
def get_<resource>_repository(db: Session = Depends(get_db)) -> <Resource>Repository
def get_<resource>_service(...) -> <Resource>Service
```

FastAPI caches `Depends()` within a single request — all providers that declare
`Depends(get_db)` share the same `Session`, which is essential for shared
transaction management.

Include a `get_current_user` provider that:
1. Extracts the Bearer token via `HTTPBearer()`
2. Validates the access token (no DB lookup)
3. Loads and returns the active `User` ORM object

---

## 11. Environment & uv Configuration (MANDATORY)

### Python version management

Use **uv** for all Python version and environment management. Never use pip,
venv, or virtualenv directly.

Required files:
- `.python-version` — pins Python version (e.g. `3.11`)
- `pyproject.toml` — single source of truth for dependencies and tooling config
- `uv.lock` — reproducible lockfile; **must be committed to version control**

### pyproject.toml structure

```toml
[project]
name = "<project>"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # runtime deps here
]

[dependency-groups]
dev = [
    "pytest>=8.2.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

### Common uv commands

```bash
uv sync                  # install production deps
uv sync --group dev      # include dev/test deps
uv run uvicorn app.main:app --reload
uv run alembic upgrade head
APP_ENV=test uv run pytest
```

### Environments

Support four environments via `APP_ENV`: `dev`, `test`, `uat`, `prod`.
Each has a separate SQLite file and loads its own `.env.<env>` file.
Never share databases across environments.

```python
_APP_ENV = os.getenv("APP_ENV", "dev")

class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///./data/{_APP_ENV}.db"
    model_config = SettingsConfigDict(env_file=f".env.{_APP_ENV}")
```

Use `@lru_cache()` on the `get_settings()` factory.

---

## 12. Migrations (Alembic)

- Use Alembic for all schema changes — never `Base.metadata.create_all()` in runtime code
- Set `render_as_batch=True` in `alembic/env.py` — required for SQLite `ALTER TABLE`
- Import all models in `alembic/env.py` so autogenerate detects all tables
- Override `sqlalchemy.url` from app settings in `env.py`, not `alembic.ini`
- Provide a hand-written initial migration (`0001_initial.py`) rather than relying
  solely on autogenerate for the first schema

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic downgrade -1
```

---

## 13. Transaction Management

- Service layer owns all `commit()` calls
- Repositories call `flush()` + `refresh()` only
- Keep transactions short — commit as soon as the mutation is complete
- `expire_on_commit=False` must be set on the session factory (see Section 4)
- Do not open nested transactions unless explicitly required

---

## 14. Testing

Use pytest with the following conventions:

- **In-memory SQLite** (`sqlite:///:memory:`) for all tests
- Use `StaticPool` to share a single connection across the session
- Create all tables via `Base.metadata.create_all()` once per test session
- Per-test isolation: yield a session inside a rolled-back transaction
- Override `get_db` via `app.dependency_overrides` in the test client fixture
- Provide fixture users at each role level and corresponding token fixtures
- Test files: `test_auth.py`, `test_<domain>.py`, `test_repositories.py`

```bash
APP_ENV=test uv run pytest
APP_ENV=test uv run pytest --cov=app --cov-report=term-missing
```

---

## 15. File Uploads (when required)

- Store files on the server filesystem; record relative paths in the DB
- Define `UPLOAD_DIR` in settings (e.g. `./data/uploads`)
- Use relative paths in the DB (e.g. `assets/<id>/image.jpg`), not absolute paths
- Validate content type and enforce a maximum file size before writing to disk
- Replace existing files atomically: remove old file, write new, then update DB
- Use async `UploadFile` in the endpoint; delegate file I/O to the service layer

---

## 16. Error Handling

- All exceptions must return consistent JSON: `{"detail": "..."}`
- Define custom `HTTPException` subclasses in `app/core/exceptions.py`
- Standard exceptions to define:
  - `InvalidCredentialsError` → 401
  - `InvalidTokenError` → 401
  - `RevokedTokenError` → 401
  - `PermissionDeniedError` → 403
  - `UserSuspendedError` → 403
  - `<Resource>NotFoundError` → 404
  - `ConflictError` → 409 (uniqueness violations, blocked deletes)
- Add a catch-all `Exception` handler in `main.py` returning 500 JSON
  (prevents HTML error pages leaking through a reverse proxy)
- Use intentionally opaque 404s for privacy-masked resources (do not reveal
  that a resource exists but is inaccessible)

---

## 17. Docker & Deployment

### Dockerfile

- Multi-stage build: `builder` (install deps with uv) → `runtime` (copy venv)
- Copy uv from the official image: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`
- Run as a non-root user
- Mount `data/` as a named Docker volume for SQLite persistence
- Set `ENV PATH="/app/.venv/bin:$PATH"` and `ENV PYTHONUNBUFFERED=1`

### CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV != "prod" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Tighten `allow_origins` to specific domains in `.env.prod`.

### Health check

Always expose a `/health` endpoint (no auth) for Docker and reverse-proxy checks:

```python
@app.get("/health")
def health_check():
    return {"status": "ok", "env": settings.APP_ENV}
```

---

## 18. Code Quality Rules

- Full type hints on all function signatures and class attributes
- No duplicated logic across layers
- Repositories: one method per distinct query
- Services: one method per distinct business operation
- Naming conventions:
  - `_enrich_<resource>(orm_obj) -> ReadSchema` — add computed/display fields
  - `_can_<action>_<resource>(resource, actor) -> bool` — permission predicates
  - `_assert_<condition>(...)` — raise if condition not met
- No inline SQL strings outside repository methods
- No business logic in routes
- No ORM queries in services

---

## 19. Anti-Patterns (STRICTLY FORBIDDEN)

**Architecture:**
- Async DB access
- ORM queries in services or routes
- Business logic in repositories or routes
- Combining ORM models and Pydantic schemas
- Importing models directly in routes

**Auth (when applicable):**
- Storing access tokens in DB
- Skipping refresh token DB validation
- Putting auth logic in routes
- Hardcoding secrets

**Datetime:**
- Using `datetime.utcnow()` — always use `datetime.now(timezone.utc)`
- Using `DateTime(timezone=True)` directly — always use `UTCDateTime`
- Using `synchronize_session=False` to paper over naive/aware comparison errors
- Returning naive datetimes from any API response

**Database:**
- `Base.metadata.create_all()` in runtime code
- Calling `commit()` in repositories
- Sharing DB files across environments
- Raw SQL strings outside repository methods

**General:**
- Hardcoded secrets or credentials anywhere in source code
- `.env.prod` committed to version control
