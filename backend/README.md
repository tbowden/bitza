# Asset Management API

FastAPI CRUD API — Phase 1: User Management & Authentication

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x (sync) |
| Database | SQLite (WAL mode, FK enforcement) |
| Auth | JWT (python-jose) + bcrypt |
| Migrations | Alembic |
| Tests | pytest + httpx TestClient |
| Runtime | Python 3.11+ |

---

## Project Structure

```
app/
  main.py                       # App factory, lifespan, CORS
  cli.py                        # Typer CLI (create-superuser)
  api/v1/
    router.py
    endpoints/
      auth.py                   # POST /auth/{login,refresh,logout}
      users.py                  # CRUD /users/
  services/
    auth_service.py             # All JWT + auth logic
    user_service.py             # All RBAC + user business logic
  repositories/
    user_repository.py          # DB reads/writes for users
    token_repository.py         # Refresh token whitelist
  models/
    user.py                     # User ORM model + UserRole enum
    token.py                    # RefreshToken ORM model
  schemas/
    user.py                     # Pydantic v2 read/write schemas
    auth.py                     # Login, token, refresh schemas
  db/
    session.py                  # Engine, WAL, FK pragma, get_db
  core/
    config.py                   # Pydantic BaseSettings (env-aware)
    security.py                 # bcrypt, JWT create/decode, JTI hash
    exceptions.py               # Custom HTTPException subclasses
    dependencies.py             # FastAPI DI providers + get_current_user

alembic/
  env.py
  versions/0001_initial.py

tests/
  conftest.py                   # In-memory DB, fixtures, token helpers
  test_auth.py
  test_users.py
  test_repositories.py
```

---

## Quick Start

### 1. Install uv (if not already installed)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Create the environment and install dependencies

```bash
# uv reads .python-version (3.11) and pyproject.toml automatically.
uv sync           # production deps only
uv sync --group dev     # include dev/test deps (needed for running tests)
```

This creates `.venv/` in the project root. You never need to activate it manually
— prefix commands with `uv run` and uv handles it.

### 3. Configure environment

```bash
# .env.dev is already present — edit SECRET_KEY before use.
```

Generate a real secret key:
```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Run migrations

```bash
uv run alembic upgrade head
```

This creates `data/dev.db` with `users` and `refresh_tokens` tables.

### 5. Create the superuser (one-time)

```bash
uv run python -m app.cli create-superuser
```

You will be prompted for email, username, display name, and password.
Only one superuser can ever exist.

### 6. Start the server

```bash
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/api/v1/docs

## Environments

| `APP_ENV` | DB file | Config file |
|---|---|---|
| `dev` | `data/dev.db` | `.env.dev` |
| `test` | in-memory | `.env.test` |
| `uat` | `data/uat.db` | `.env.uat` |
| `prod` | `data/prod.db` | `.env.prod` |

Switch environments with:
```bash
APP_ENV=uat alembic upgrade head
APP_ENV=uat uvicorn app.main:app
```

---

## Authentication Flow

### Login
```
POST /api/v1/auth/login
{"identifier": "user@example.com", "password": "..."}   # or username

→ {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

- `identifier` accepts either email or username (case-insensitive).
- Access token: 15 min, stateless (not stored in DB).
- Refresh token: 30 days, stored as `SHA256(jti)` in `refresh_tokens` table.

### Authenticated request
```
GET /api/v1/users/me
Authorization: Bearer <access_token>
```

### Refresh (token rotation)
```
POST /api/v1/auth/refresh
{"refresh_token": "..."}

→ new {"access_token": "...", "refresh_token": "..."}
```
The old refresh token is immediately revoked. Replaying it returns 401.

### Logout
```
POST /api/v1/auth/logout
{"refresh_token": "..."}

→ 204 No Content
```

---

## User Roles & Permissions

| Action | superuser | admin | user |
|---|---|---|---|
| Create superuser | CLI only | ✗ | ✗ |
| Create admin | ✓ | ✗ | ✗ |
| Create user | ✓ | ✓ | ✗ |
| List all users | ✓ | ✓ | ✗ |
| View any user | ✓ | ✓ | own only |
| Update user details | ✓ | users only | ✗ |
| Suspend a user | ✓ | users only | ✗ |
| Change role | ✓ | ✗ | ✗ |
| Delete user | ✓ | ✗ | ✗ |
| Update own profile | ✓ | ✓ | ✓ |
| Can be suspended | ✗ | ✓ | ✓ |

No self-registration. All accounts are created by admins or the superuser.

---

## API Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Login (email or username) |
| POST | `/api/v1/auth/refresh` | Refresh token rotation |
| POST | `/api/v1/auth/logout` | Revoke refresh token |

### Users
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/users/me` | Any | Get own profile |
| PATCH | `/api/v1/users/me` | Any | Update own display_name / password |
| GET | `/api/v1/users/` | Admin+ | List users |
| POST | `/api/v1/users/` | Admin+ | Create user |
| GET | `/api/v1/users/{id}` | Admin+ / own | Get user |
| PATCH | `/api/v1/users/{id}` | Admin+ | Update user |
| DELETE | `/api/v1/users/{id}` | Superuser | Delete user |

### System
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (no auth) |

---

## Running Tests

```bash
# Install dev dependencies first (includes pytest, httpx, etc.)
uv sync --group dev

APP_ENV=test uv run pytest
```

Tests use an in-memory SQLite database. The `get_db` dependency is overridden
so each test runs in a rolled-back transaction — no state bleeds between tests.

```bash
APP_ENV=test uv run pytest --cov=app --cov-report=term-missing   # with coverage
```

---

## Docker Deployment

### Build & run

```bash
# Copy and fill in your production env file
cp .env.prod.template .env.prod
# Edit .env.prod — set a real SECRET_KEY

docker compose up -d --build
```

### nginx reverse proxy

The app container is not exposed externally. Add to your nginx config:

```nginx
location /api/ {
    proxy_pass http://assetmgmt_app:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The `docker-compose.yml` joins the `nginx_proxy_network` external network.
Change the `name:` field under `proxy_network:` to match your existing setup.

### Data persistence

The SQLite file lives in the `assetmgmt_data` named Docker volume, mounted at
`/app/data/prod.db`. It survives container restarts and image rebuilds.

### Create superuser in Docker

```bash
docker compose exec app uv run python -m app.cli create-superuser
```

### Run migrations in Docker

Migrations run automatically on container startup (in the CMD). To run them
manually:

```bash
docker compose exec app uv run alembic upgrade head
```

---

## Security Notes

- **Refresh token storage**: only `SHA256(jti)` is stored — a raw DB dump
  cannot be replayed without also knowing `SECRET_KEY`.
- **Access tokens**: never stored in DB; validated stateless on every request.
- **Token rotation**: every refresh call revokes the old token and issues a new
  pair. Replay of an old refresh token returns 401.
- **Suspension**: suspended users are rejected at both login and on every
  authenticated request (access-token validation re-checks `is_active`).
- **Superuser**: cannot be suspended via API. Cannot be deleted. Can only be
  created via CLI.

---

## Migrations

Generate a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

Downgrade:

```bash
alembic downgrade -1
```

SQLite `ALTER TABLE` is handled via `render_as_batch=True` in `alembic/env.py`.
