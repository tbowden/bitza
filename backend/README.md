# Bitza asset management API

A REST API for tracking the location, quantity, and details of physical assets —
electronic components, tools, and other items stored across named locations.

> **Getting started?** See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step
> setup instructions covering local development, Docker UAT, and production.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x (sync) |
| Database | SQLite (WAL mode, FK enforcement) |
| Auth | JWT (python-jose) + bcrypt + zxcvbn |
| Migrations | Alembic |
| Tests | pytest + httpx TestClient |
| Runtime | Python 3.12+ managed by uv |

---

## Project structure

```
app/
  main.py                       # App factory, lifespan, CORS
  cli.py                        # Typer CLI (create-superuser)
  api/v1/
    router.py
    endpoints/
      auth.py                   # POST /auth/{login,refresh,logout}
      users.py                  # CRUD /users/
      locations.py              # CRUD /locations/ + nested details
      assets.py                 # CRUD /assets/, transactions, audit, categories
  services/
    auth_service.py
    user_service.py
    location_service.py
    asset_service.py
  repositories/
    user_repository.py
    token_repository.py
    location_repository.py
    asset_repository.py
    category_repository.py
  models/
    base.py                     # UTCDateTime TypeDecorator
    user.py
    token.py
    location.py
    asset.py
  schemas/
    auth.py
    user.py
    location.py
    asset.py
  db/
    session.py
  core/
    config.py
    security.py
    exceptions.py
    dependencies.py

alembic/
  versions/
    0001_initial.py             # users + refresh_tokens
    0002_assets.py              # locations, assets, transactions, audit
```

---

## User roles and permissions

| Action | superuser | admin | user |
|---|---|---|---|
| Create superuser | CLI only | ✗ | ✗ |
| Create admin | ✓ | ✗ | ✗ |
| Create user | ✓ | ✓ | ✗ |
| List / view any user | ✓ | ✓ | own only |
| Update user details | ✓ | users only | ✗ |
| Suspend a user | ✓ | users only | ✗ |
| Change role | ✓ | ✗ | ✗ |
| Delete user | ✓ | ✗ | ✗ |
| Update own profile | ✓ | ✓ | ✓ |
| Can be suspended | ✗ | ✓ | ✓ |

No self-registration — all accounts are created by admins or the superuser.

---

## API endpoints

### Auth

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Login with email or username |
| POST | `/api/v1/auth/refresh` | Refresh token rotation |
| POST | `/api/v1/auth/logout` | Revoke refresh token |

### Users

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/users/me` | Any | Get own profile |
| PATCH | `/api/v1/users/me` | Any | Update own display name / password |
| GET | `/api/v1/users/` | Admin+ | List users |
| POST | `/api/v1/users/` | Admin+ | Create user |
| GET | `/api/v1/users/{id}` | Admin+ / own | Get user |
| PATCH | `/api/v1/users/{id}` | Admin+ | Update user |
| DELETE | `/api/v1/users/{id}` | Superuser | Delete user |

### Locations

| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/v1/locations/` | List / create storage locations |
| GET/PATCH/DELETE | `/api/v1/locations/{id}` | Manage a location |
| GET/POST | `/api/v1/locations/{id}/details` | List / create sub-locations |
| GET/PATCH/DELETE | `/api/v1/locations/{id}/details/{id}` | Manage a sub-location |

### Assets

| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/v1/assets/` | List / create assets |
| GET/PATCH/DELETE | `/api/v1/assets/{id}` | Manage an asset |
| POST | `/api/v1/assets/{id}/image` | Upload / replace image |
| GET/POST | `/api/v1/assets/{id}/transactions` | Stock history / add movement |
| GET/POST | `/api/v1/categories/` | List / create categories |
| PATCH/DELETE | `/api/v1/categories/{id}` | Manage a category |
| GET | `/api/v1/audit/` | Audit log (admin+ only) |

### System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (no auth) |

Interactive docs (when running): http://localhost:8000/api/v1/docs

---

## Authentication

Login accepts either email or username:

```
POST /api/v1/auth/login
{"identifier": "user@example.com", "password": "..."}

→ {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

- Access token: 15 min, stateless (not stored in DB)
- Refresh token: 30 days, stored as `SHA256(jti)` in the DB
- Rotation: every refresh call revokes the old token and issues a new pair

### Password policy

- Minimum 12 characters, maximum 128
- Must achieve a zxcvbn strength score of 3 or higher
- Checked against the HIBP breach database when `CHECK_PWNED_PASSWORDS=true`
  (intended for public-facing deployments)

---

## Location privacy

Storage locations and sub-locations can be marked private. Privacy cascades
downward — a private location makes everything inside it private regardless
of the sub-location's own setting.

| Who can see a private resource | |
|---|---|
| Superuser | Always |
| Owner | Always |
| Admin | Only if the resource is shared |
| Other users | Never |

---

## Running tests

```bash
uv sync --group dev
APP_ENV=test uv run pytest
APP_ENV=test uv run pytest --cov=app --cov-report=term-missing
```

---

## Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Generate a migration after model changes
uv run alembic revision --autogenerate -m "describe change"

# Roll back one migration
uv run alembic downgrade -1
```
