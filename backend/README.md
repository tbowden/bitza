# Bitza API

A REST API for tracking physical stuff — electronic components, tools and
other items — with who is responsible for it, where it is, who has it, and
(for consumables) how many are left. One unified data model (Projects and
Bitzas) serves both a home workshop and a club with rotating membership.

> **Getting started?** See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step
> setup covering local development, Docker UAT, and production.
>
> **Design and API contract:** the full domain model, every endpoint shape and
> the reasoning behind each decision live in
> [`../bitza_project_context.md`](../bitza_project_context.md). This README is
> only an overview; if the two ever disagree, that document (and the live
> `/api/v1/docs`) wins.

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
| Runtime | Python 3.14+ managed by uv |

---

## Project structure

```
app/
  main.py                       # App factory, lifespan, CORS
  cli.py                        # Typer CLI (create-superuser)
  api/v1/
    router.py
    endpoints/
      auth.py                   # /auth/{login,refresh,logout}
      users.py                  # /users/ (+ /me, /directory)
      projects.py               # /projects/ (+ /mine, members)
      bitzas.py                 # /bitzas/ (tree, checkout, stock, images,
                                #   documents), /categories/, /checkouts/mine
      audit.py                  # /audit/
  services/                     # auth_, user_, project_, bitza_service
  repositories/                 # one per table (user, token, project, bitza,
                                #   checkout, stock_log, bitza_image,
                                #   bitza_document, category, audit, system_config)
  models/                       # SQLAlchemy models (base.py has UTCDateTime)
  schemas/                      # Pydantic request/response models
  db/session.py
  core/
    config.py                   # Settings (env-driven)
    security.py
    exceptions.py
    dependencies.py
    file_types.py               # content sniffing for uploads

alembic/versions/
  0001_initial.py               # users + refresh_tokens
  0002_bitzas.py                # teams (later renamed projects), bitzas, checkouts, stock logs
  0003_system_config.py         # singleton root-bitza pointer
  0004_rename_team_to_project.py
  0005_bitza_documents.py       # datasheets / SDS / manuals
tests/
```

---

## User roles

Three roles: `superuser`, `admin`, `user`. Roles govern **account management
only**; inside the Project/Bitza model everyone can do (nearly) everything by
design, with one exception — hard-deleting a bitza is admin/superuser only.

| Action | superuser | admin | user |
|---|---|---|---|
| Create superuser | CLI only | ✗ | ✗ |
| Create admin | ✓ | ✗ | ✗ |
| Create user | ✓ | ✓ | ✗ |
| Change a role | ✓ | ✗ | ✗ |
| Suspend / delete a user | ✓ | plain users only | ✗ |
| View the user list and audit log | ✓ | ✓ | ✗ |
| Update own profile | ✓ | ✓ | ✓ |
| Hard-delete a bitza | ✓ | ✓ | ✗ |

No self-registration — all accounts are created by admins or the superuser.
The detailed rules (including nobody acting on their own account) are in
`bitza_project_context.md`.

---

## API at a glance

All under `/api/v1`. Interactive docs when running:
http://localhost:8000/api/v1/docs

| Area | Paths |
|---|---|
| Auth | `/auth/login`, `/auth/refresh`, `/auth/logout` |
| Users | `/users/`, `/users/me`, `/users/directory`, `/users/{id}` |
| Projects | `/projects/`, `/projects/mine`, `/projects/{id}`, `/projects/{id}/members[/{user_id}]` |
| Bitzas | `/bitzas/`, `/bitzas/{id}`, `…/ancestors`, `…/retire`, `…/reactivate`, `…/reassign-project` |
| Checkout | `/bitzas/{id}/checkout`, `…/checkin`, `…/checkouts`; `/checkouts/mine` |
| Stock | `/bitzas/{id}/stock-adjustments` |
| Images | `/bitzas/{id}/images[/{image_id}]` |
| Documents | `/bitzas/{id}/documents[/{document_id}]` |
| Categories | `/categories/`, `/categories/{id}` |
| Audit | `/audit/` (admin+) |
| System | `/health` (root, no auth) |

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

## File uploads

Images and documents are stored on the server filesystem under `UPLOAD_DIR`
(default `./data/uploads`); the database records only the relative path.

- **Images:** JPEG, PNG, GIF or WebP, max 10 MB.
- **Documents:** PDF, common images, ZIP, Word/Excel/PowerPoint
  (OOXML), OpenDocument and plain text, max `MAX_DOCUMENT_BYTES` (default 50 MB).
- **The file's type is determined from its content**, not from the client's
  `Content-Type` or filename (`app/core/file_types.py`). Anything else is
  rejected with `415`. The detected type is what gets stored and served.
- If a reverse proxy sits in front of the API, its request-body limit must be
  at least the largest upload (see [DEPLOYMENT.md](DEPLOYMENT.md)).
- **Back up `UPLOAD_DIR` together with the database** — they live in the same
  volume.

---

## Running tests

```bash
uv sync --group dev
APP_ENV=test uv run pytest -W error          # -W error: how the suite is verified
APP_ENV=test uv run pytest --cov=app --cov-report=term-missing
```

---

## Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Generate a migration after model changes
uv run alembic revision --autogenerate -m "describe change"

# Check the models and migrations agree (needs an up-to-date database)
uv run alembic check

# Roll back one migration
uv run alembic downgrade -1
```
