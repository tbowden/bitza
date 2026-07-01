# FastAPI CRUD API — Project context instructions

General-purpose system instructions for building production-disciplined CRUD
APIs using FastAPI, SQLAlchemy (sync), SQLite, and uv. These instructions apply
to any domain — user management, asset tracking, inventory, content management,
etc. Auth and JWT sections apply only when authentication is required.

---

## 1. Core technology stack (MANDATORY)

- Python 3.12+ managed by **uv** (see Section 12)
- FastAPI (latest stable)
- SQLAlchemy 2.x — **synchronous DB access only** (see Section 9 for when async is appropriate)
- Pydantic v2
- SQLite — no external database (with SpatiaLite extension when required for spatial data)
- Alembic for migrations
- pytest for testing
- JWT: `python-jose` + `bcrypt` (when auth is required)
- `zxcvbn` for password strength checking (when auth is required)
- `httpx` for external HTTP calls (async client only — see Section 9)

**DO NOT:**
- Use async SQLAlchemy or async DB sessions
- Use SQLModel
- Use external services (Redis, queues, etc.)
- Use `passlib` — use `bcrypt` directly (passlib breaks on bcrypt >= 4.1)

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
- Methods that perform external I/O (HTTP calls, file writes) must be `async def`
  (see Section 9); all other service methods remain synchronous

**Repositories:**
- No business logic
- DB interaction only: reads, writes, deletes
- Use `flush()` not `commit()` — the service layer owns transaction boundaries
- Return ORM model instances
- Always synchronous — repositories never use async/await

**DB layer:**
- Session and engine management only

---

## 3. Required project structure

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
    security.py              # bcrypt, JWT utils, password validation (if auth required)
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

## 4. Database configuration (SQLite)

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

### Hierarchical / self-referential data

For tree structures (e.g. a recursive location hierarchy), use an adjacency
list — a nullable `parent_id` FK pointing to the same table. Do not use
nested sets, closure tables, or graph/document stores.

Design queries to target direct parent-child relationships wherever possible
(single non-recursive `WHERE parent_id = ?` queries). Reserve `WITH RECURSIVE`
CTEs for the rare cases where ancestor path resolution is genuinely needed
(e.g. building a display breadcrumb). Never perform full subtree traversal
on the backend — the frontend should drive recursive exploration via multiple
direct-children requests, each fetching one level at a time.

---

## 5. Schema design (Pydantic v2)

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

## 6. Authentication — JWT hybrid (when required)

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

- Evaluate password strength using `zxcvbn`. A password is only acceptable
  if it achieves a score of 3 or higher (0–4 scale).
- Minimum length: 12 characters. Maximum: 128 characters.
- Do not use composition rules (uppercase, digits, symbols) as the primary
  strength mechanism — zxcvbn is the gate.
- Check passwords against the HIBP k-anonymity API unless the app is expected
  to run on a non-public-facing network. Implement via `httpx.AsyncClient`
  (see Section 9). Gate behind `CHECK_PWNED_PASSWORDS: bool = False` in
  settings so it can be enabled for public deployments without code changes.
- The breach check must **fail open** on network errors — a transient HIBP
  outage must never prevent a legitimate password change.
- Backend validation is authoritative. Frontend validation (also using `zxcvbn`)
  is advisory only — provides real-time feedback but does not block submission.

### Security rules

- Include `jti` in all tokens
- Enforce `type` claim — reject refresh tokens used as access tokens and vice versa
- Hash JTIs with `SHA256` before DB storage
- Superuser: cannot be suspended; created via CLI only, never via API
- Implement expired-token cleanup on startup and/or periodically

---

## 7. Repository layer rules

- Accept a `Session` in `__init__`
- Return ORM model instances
- Use `flush()` — never `commit()`
- No business logic, no permission checks
- No raw SQL strings outside repository methods (use SQLAlchemy constructs)
- Always synchronous — repositories never use async/await

---

## 8. Service layer rules

- No direct ORM queries — use repositories only
- Own all `commit()` calls — repositories only flush
- Enforce all business rules and permission checks
- Use private `_enrich_*` methods to add denormalised/computed fields to read schemas
- Use private `_can_*` methods to encapsulate permission logic
- Raise custom `HTTPException` subclasses (from `app/core/exceptions.py`)
- Write audit log entries for significant mutations if an audit log is in scope
- Methods that perform external I/O (HTTP calls, file writes) must be `async def`
  (see Section 9); all other service methods remain synchronous

---

## 9. Sync vs async

### The core rule

**SQLAlchemy is always synchronous.** The DB engine, session, and all repository
methods are sync. This is a hard requirement — do not use async SQLAlchemy.

**FastAPI supports both sync and async route handlers and service methods.**
The framework runs sync handlers in a thread pool and async handlers on the
event loop. Both work correctly alongside a sync DB session.

### When to use async

Use `async def` only when the operation involves non-DB I/O that would otherwise
block the event loop:

- External HTTP calls (e.g. HIBP breach check, third-party APIs)
- File I/O in hot paths (prefer `aiofiles` for large uploads)
- Any `await`-able operation

Do **not** use async for:
- Repository methods (always sync)
- Service methods that only call repositories (always sync)
- Route handlers that only call sync services (keep them sync)

### The narrow async boundary pattern

Keep the async surface as small and explicit as possible. A common pattern
is one async helper in `security.py` or `core/`, called by a small number
of async service methods, with the rest of the stack remaining sync:

```python
# core/security.py — async only because of the HTTP call
async def check_pwned_password(password: str) -> None:
    if not settings.CHECK_PWNED_PASSWORDS:
        return
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
        ...

# services/user_service.py — async only because it calls the above
async def create_user(self, data: UserCreate, ...) -> User:
    await validate_password(data.password)   # async boundary
    user = self._user_repo.create(...)       # sync DB access, no await
    self._db.commit()                        # sync
    return user

# api/v1/endpoints/users.py — async because it calls an async service method
async def create_user(body: UserCreate, ...) -> User:
    return await user_service.create_user(data=body, ...)
```

### Async in the CLI

The CLI (Typer) is synchronous. Call async service methods from the CLI using
`asyncio.run()`, which creates and manages a fresh event loop:

```python
import asyncio

def create_superuser_command(...) -> None:
    async def _run():
        user = await service.create_superuser(...)
    asyncio.run(_run())
```

Never call `asyncio.run()` inside a route handler or any other async context —
it will raise a `RuntimeError` because an event loop is already running.

### External HTTP calls

Always use `httpx.AsyncClient` for external HTTP calls, never `requests` or
the sync `httpx` client:

```python
async with httpx.AsyncClient(timeout=5.0) as client:
    response = await client.get(url)
```

Set an explicit timeout. Always handle network errors gracefully — external
services are unreliable and must not break core application functionality.

---

## 10. API layer rules

- No business logic — call service, return result
- Use `response_model` on every endpoint
- Use `Depends()` for all dependencies — never instantiate services or repos directly
- Document status codes with `responses={}` on non-obvious endpoints
- Use appropriate HTTP status codes:
  - `201` for creation
  - `204` for delete / logout (no body)
  - `404` for not-found
  - `409` for uniqueness conflicts or blocked deletes
- Route handlers are `async def` only when they call an async service method;
  otherwise keep them `def` (sync handlers run in FastAPI's thread pool, which
  is appropriate when the underlying work is synchronous DB access)

---

## 11. Dependency injection

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

## 12. Environment & uv configuration (MANDATORY)

### Python version management

Use **uv** for all Python version and environment management. Never use pip,
venv, or virtualenv directly.

Required files:
- `.python-version` — pins Python version (e.g. `3.12`)
- `pyproject.toml` — single source of truth for dependencies and tooling config
- `uv.lock` — reproducible lockfile; **must be committed to version control**

### pyproject.toml structure

```toml
[project]
name = "<project>"
version = "0.1.0"
requires-python = ">=3.12"
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

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = false
ignore_missing_imports = true

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

### Environment file conventions

- `.env.test` — tracked in git (never contains sensitive values)
- `.env.dev.template`, `.env.uat.template`, `.env.prod.template` — tracked in git (placeholders only)
- `.env.dev`, `.env.uat`, `.env.prod` — gitignored; generated locally from templates
- The placeholder `SECRET_KEY` in `.env.dev.template` is acceptable for pure
  localhost development. Set a real key if running with `--host 0.0.0.0`.

---

## 13. Migrations (Alembic)

- Use Alembic for all schema changes — never `Base.metadata.create_all()` in runtime code
- Set `render_as_batch=True` in `alembic/env.py` — required for SQLite `ALTER TABLE`
- Import all models in `alembic/env.py` so autogenerate detects all tables
- Override `sqlalchemy.url` from app settings in `env.py`, not `alembic.ini`
- Provide a hand-written initial migration (`0001_initial.py`) rather than relying
  solely on autogenerate for the first schema

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic downgrade -1
```

---

## 14. Transaction management

- Service layer owns all `commit()` calls
- Repositories call `flush()` + `refresh()` only
- Keep transactions short — commit as soon as the mutation is complete
- `expire_on_commit=False` must be set on the session factory (see Section 4)
- Do not open nested transactions unless explicitly required

---

## 15. Testing

Use pytest with the following conventions:

- **In-memory SQLite** (`sqlite:///:memory:`) for all tests
- Use `StaticPool` to share a single connection across the session
- Create all tables via `Base.metadata.create_all()` once per test session
- Per-test isolation: yield a session inside a rolled-back transaction
- Override `get_db` via `app.dependency_overrides` in the test client fixture
- Provide fixture users at each role level and corresponding token fixtures
- Test files: `test_auth.py`, `test_<domain>.py`, `test_repositories.py`
- CLI tests: use `typer.testing.CliRunner` with a monkeypatched `SessionLocal`
  pointing at a per-test on-disk SQLite database (not the in-memory one, since
  the CLI manages its own session internally)

```bash
APP_ENV=test uv run pytest
APP_ENV=test uv run pytest --cov=app --cov-report=term-missing
```

---

## 16. File uploads (when required)

- Store files on the server filesystem; record relative paths in the DB
- Define `UPLOAD_DIR` in settings (e.g. `./data/uploads`)
- Use relative paths in the DB (e.g. `items/<id>/photo.jpg`), not absolute paths
- Validate content type and enforce a maximum file size before writing to disk
- Replace existing files atomically: remove old file, write new, then update DB
- Use async `UploadFile` in the endpoint; delegate file I/O to the service layer
- Serve uploaded files via an authenticated endpoint (not as static files) so
  access control applies. Use `FileResponse` with `mimetypes.guess_type()` for
  the content type. Angular clients must fetch images via `HttpClient` with
  `{ responseType: 'blob' }` and create a blob URL — plain `<img src>` tags
  will not send the Authorization header.

---

## 17. Error handling

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

---

## 18. Docker & deployment

### Dockerfile

- Multi-stage build: `builder` (install deps with uv) → `runtime` (copy venv)
- Copy uv from the official image: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/`
- Run as a non-root user
- Mount `data/` as a named Docker volume for SQLite persistence
- Set `ENV PATH="/app/.venv/bin:$PATH"` and `ENV PYTHONUNBUFFERED=1`
- Use `python:3.12-slim` as the base image

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

## 19. Code quality rules

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

## 20. Anti-patterns (STRICTLY FORBIDDEN)

**Architecture:**
- Async DB access or async SQLAlchemy
- ORM queries in services or routes
- Business logic in repositories or routes
- Combining ORM models and Pydantic schemas
- Importing models directly in routes

**Async:**
- Blocking the event loop with sync HTTP calls in async contexts — use
  `httpx.AsyncClient` instead of `requests` or the sync `httpx` client
- Making route handlers or service methods `async def` solely because it
  "seems better" — async is only justified when there is actual non-DB I/O
- Calling `asyncio.run()` inside a route handler or any running async context
  (raises `RuntimeError` — use it only in CLI/sync entry points)
- Forgetting to make a route handler `async def` when it calls an async
  service method (causes `RuntimeError: coroutine was never awaited`)

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
- Full subtree traversal on the backend for hierarchical data — let the
  frontend drive recursive exploration via multiple direct-children requests

**General:**
- Hardcoded secrets or credentials anywhere in source code
- `.env.prod` committed to version control
