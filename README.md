# bitza
A tracker for physical stuff — electronic components, tools and other items:
where it is, who is responsible for it, who has it, and how many are left.
Started as a home workshop tool and now also suits clubs with rotating
membership.

**New here (or a new Claude chat)?** Start with
[`bitza_context_restoration.md`](bitza_context_restoration.md).

## Backend API

FastAPI + SQLite, Python 3.14 managed by uv. See [backend/README.md](backend/README.md)
for an overview or [backend/DEPLOYMENT.md](backend/DEPLOYMENT.md) for setup and
deployment. Full design and API contract: [`bitza_project_context.md`](bitza_project_context.md).

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.cli create-superuser
uv run uvicorn app.main:app --reload
```

## Frontend Angular app

Angular 22 + Angular Material, in `frontend/bitza`. Built and in use against a
live backend; documents (datasheets/SDS) are the one backend feature it does
not use yet. See [`bitza_frontend_context.md`](bitza_frontend_context.md).

```bash
cd frontend/bitza
nvm use        # reads ../.nvmrc
npm ci
npm start      # same as: npx ng serve
```

`ng` is an npm binary: run it through `npm start`/`npx` from `frontend/bitza`.
(`uv run ng serve` will not work — uv is for the backend only.)
