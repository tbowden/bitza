# Bitza — context restoration

**Purpose of this document:** this is the "start here" briefing for a new
chat picking up work on Bitza. It tells you what stage the project is at,
where to find the detailed design/API contract, and what's expected next.
It is deliberately short — for the full domain model, API shapes, and the
reasoning behind every design decision, see **`bitza_project_context.md`**
(also at repo root). Read that document before writing any frontend code
against the API; this one just orients you.

If you are a fresh Claude instance reading this for the first time: welcome.
Read this file, then read `bitza_project_context.md` in full before doing
anything else. Do not assume you already know the API shape from general
FastAPI conventions — several of Bitza's design choices (no ownership
model, retire-vs-delete, team reassignment cascade, checkout as derived
state) are deliberate and non-obvious, and are documented there.

---

## What Bitza is (one paragraph)

A tracker for physical stuff — originally home workshop components and
tools, now generalised to also serve community or student clubs with
rotating membership and multiple potentially overlaping teams or projects. 
One unified data model serves both; the club case is simply the richer end of 
the same schema. Backend: FastAPI + SQLite. Frontend: Angular (not yet developed).

---

## Stage tracker

| Stage | Scope | Status |
|---|---|---|
| **1** | Auth, users, roles (superuser/admin/user), JWT refresh/rotation, password policy | ✅ Done, tested, untouched since |
| **2** | Unified `Team`/`Bitza` backend model — replaces the original `StorageLocation`/`LocationDetail`/`Asset` design entirely | ✅ Done, tested (58/58 passing: Phase 1 unaffected + full new Team/Bitza suite) |
| **3** | Angular frontend | 🔲 Not started — this is the next piece of work |

Stage 2 was a full rebuild, not an incremental migration — there was no
production data, so the old location/asset tables and endpoints were
deleted outright rather than migrated. See `MIGRATION_NOTES.md` (backend
root) if anything about the old shape ever needs to be dug up from history.

---

## Repo structure (as of end of Stage 2)

```
bitza/
├── README.md
├── bitza_project_context.md        ← full design doc, API contract, read this next
├── bitza_context_restoration.md     ← this file
├── backend/
│   ├── AI_instructions.md          ← general FastAPI/SQLAlchemy/uv conventions used throughout
│   ├── MIGRATION_NOTES.md          ← what got deleted/replaced during the Stage 2 rebuild
│   ├── app/
│   │   ├── models/      team.py, bitza.py, category.py, audit.py, user.py, token.py, base.py
│   │   ├── schemas/     team.py, bitza.py, category.py, audit.py, user.py, auth.py
│   │   ├── repositories/  one per model, thin DB access only
│   │   ├── services/    team_service.py, bitza_service.py (also owns categories + audit reads),
│   │   │                auth_service.py, user_service.py
│   │   ├── api/v1/endpoints/  teams.py, bitzas.py (also owns /categories), audit.py, auth.py, users.py
│   │   └── core/        config.py, security.py, exceptions.py, dependencies.py
│   ├── alembic/versions/  0001_initial.py (users/tokens), 0002_bitzas.py (everything else)
│   └── tests/  test_auth.py, test_users.py, test_cli.py, test_repositories.py (all Phase 1,
│                unchanged), test_teams.py, test_bitzas.py (Stage 2, new)
└── frontend/                        ← does not exist yet — Stage 3 starts here
```

---

## The API surface, condensed

Full detail (request/response shapes, validation rules, permission model,
the design rationale behind each choice) is in `bitza_project_context.md`.
This is just enough to orient a frontend build without re-reading the
whole thing up front:

- **Auth** — `POST /api/v1/auth/{login,refresh,logout}`, dual JWT
  (15 min access / 30 day refresh, rotational), single `identifier` field
  accepting email or username.
- **Users** — `GET/PATCH /api/v1/users/me`, admin/superuser-gated
  `/api/v1/users/` CRUD. Roles: `superuser` / `admin` / `user` — this is
  the **only** place real access control exists in the whole app.
- **Teams** — `/api/v1/teams/`, fully open (any authenticated user can
  create/edit/delete a team and add/remove *any* user from *any* team —
  deliberate trust model, not an oversight). `Team` doubles as "Project"
  in the frontend's own display labelling; nothing in the API encodes
  that distinction.
- **Bitzas** — `/api/v1/bitzas/`, the unified location/container/item
  tree (`kind`: `fixed` / `mobile` / `stock`). Also open to any
  authenticated user for create/edit/move/retire/checkout/stock, **except
  hard delete**, which is admin/superuser only. Key sub-resources:
  `/retire`, `/reactivate`, `/reassign-team` (cascade sweep), `/checkout`,
  `/checkin`, `/checkouts`, `/stock-adjustments`, `/images`.
- **Categories** — `/api/v1/categories/`, unchanged simple CRUD, lives in
  the same router file as bitzas.
- **Audit log** — `/api/v1/audit/`, admin/superuser only — the one read
  endpoint in the whole app that's permission-gated.

**There is no privacy/visibility model anywhere.** Every bitza, team, and
location is visible to every authenticated user. This was deliberately
removed during Stage 2 design — see `bitza_project_context.md` if this
looks surprising.

---

## Frontend-relevant decisions already made (don't re-litigate these)

- **Team vs Project is a pure display-label config**, decided at the
  Angular level (env file or runtime setting — exact mechanism not yet
  decided, see "open questions" below). The API is always `Team`.
- **Token refresh**: interceptor-based is the stated preference (not yet
  built) — transparent 401 → refresh → retry, redirect to login only if
  refresh itself fails.
- **Image fetching requires `HttpClient` with `responseType: 'blob'`** —
  plain `<img src="...">` will not send the Authorization header against
  `GET /api/v1/bitzas/{id}/images/{image_id}`.
- **Reassign-team's `cascade_scope` has no backend default** — the
  frontend is expected to supply a sensible default based on the bitza's
  `kind` (e.g. a cupboard defaults its scope picker to `none`, a toolbox
  to `all_descendants`), but the API itself never infers one; see
  `bitza_project_context.md` for why.
- **Direct-children-only reads**: `GET /bitzas/?parent_id=X` never
  recurses. Any "show me everything nested here" UI has to drive that
  itself with repeated calls — this is deliberate, not a limitation to
  work around on the backend.

## Open questions for Stage 3 (frontend) — not yet decided

- Session persistence (localStorage vs sessionStorage)
- Where the Team/Project label toggle actually lives in the Angular build
- Whether the frontend infers `cascade_scope` defaults automatically from
  `kind`, or always asks the user explicitly
- Component library / styling approach — nothing chosen yet
- Whether to scaffold with the Angular CLI directly or via `ng new` with
  specific options (routing, SCSS, standalone components, etc.) — no
  decisions made, wide open

## Deliberately deferred — do not build unless asked

- **In-app barcode/serial scanner** for manufacturer/supplier codes that
  can't be replaced with a Bitza-generated QR label. The *primary* scan
  mechanism (a QR/NFC tag encoding `bitza.myclub.org.au/bitza/<id>/`)
  needs no scanner at all — that's just a route + a rendered QR image and
  should be built as part of normal Stage 3 work. The camera-based
  fallback scanner is the deferred piece.
- **Comp/trip packing lists** ("what needs to go to Melbourne this
  year") — no backend support exists for this yet, by design.

---

## How to get further detail without re-deriving it

- **Full domain model, every schema/endpoint shape, and the reasoning
  behind each design decision** → `bitza_project_context.md`
- **General FastAPI/SQLAlchemy/uv conventions this backend follows**
  (layering rules, sync-vs-async policy, testing conventions, etc.) →
  `backend/AI_instructions.md`
- **What got deleted/replaced during the Stage 2 rebuild, if old history
  ever needs digging up** → `backend/MIGRATION_NOTES.md`
