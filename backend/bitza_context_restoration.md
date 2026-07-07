# Bitza — context restoration document

Use this document at the start of a new chat to restore full project context.
Upload this document alongside the FastAPI context instructions and the Bitza
project context document.

---

## What Bitza is

An asset and stock custody and storage tracking system. Originally conceived as a
home inventory tracker ("bitza this and bitza that"), now designed to also
serve clubs and organisations with ad-hoc team or project based asset or 
inventory tracking.

**Two deployments, one codebase:**
- Home deployment — a handful of users, track components and tools across
  rooms and storage containers
- Club deployment — student teams, shared workshop, tools and consumables
  managed by team responsibility rather than individual ownership

The Angular frontend is not yet started. All work to date is backend only.

**Project location:** `bitza/backend/` within a monorepo (`bitza/frontend/`
reserved for Angular).

---

## Current state of the codebase

### What's built and tested (do not change)

**Phase 1 — auth and user management.** Fully built, 103 tests passing,
production-ready. This entire layer is settled and should not be touched
during the Phase 2 redesign.

Files:
- `app/models/user.py`, `app/models/token.py`
- `app/schemas/auth.py`, `app/schemas/user.py`
- `app/repositories/user_repository.py`, `app/repositories/token_repository.py`
- `app/services/auth_service.py`, `app/services/user_service.py`
- `app/api/v1/endpoints/auth.py`, `app/api/v1/endpoints/users.py`
- `app/cli.py` (create-superuser command with delete-and-replace flow)
- `alembic/versions/0001_initial.py`
- `tests/test_auth.py`, `tests/test_users.py`, `tests/test_repositories.py`,
  `tests/test_cli.py`

**Phase 2 — locations and assets.** Built but being completely redesigned.
The existing Phase 2 code (`app/models/location.py`, `app/models/asset.py`,
their repos, services, endpoints, and `alembic/versions/0002_assets.py`)
will be replaced. The existing Phase 2 tests (`tests/test_assets.py`) will
also be replaced. Do not build on top of the existing Phase 2 code — it is
being discarded.

### Current version

`v0.1.10` — `pyproject.toml`, Python 3.12, uv-managed.

---

## The redesign — what's been agreed

### Core philosophy

This is a **scan-driven custody and storage system**, not an inventory
management system. It answers two questions:

1. Where is this item right now?
2. Where should it go when not in use?

It explicitly does **not** do: audit-grade history, approval workflows,
reservations, return deadlines, cost tracking, or complex permission systems
at the item level. The existing auth/user permission system (superuser/admin/user)
stays exactly as-is.

Prefer "good enough and current" over "complete and historical."

### The unified Thing model

The key insight: storage locations and items are the same kind of entity.
A toolbox is a location when you look inside it, and a trackable item when
you ask who has it. Collapse both into one self-referential `Thing` table
with a `mobility` discriminator.

**Thing table:**

| Field | Notes |
|---|---|
| id, name, description | |
| parent_id | Nullable FK → Thing.id (adjacency list, arbitrary depth) |
| responsible_team_id | Nullable FK → Team. Cascades from nearest ancestor that has one set; overrideable at any depth. Purely informational — no permission gating. |
| scan_tag | Nullable, unique. NFC UID or generated QR code. Any level can have one. |
| tag_source | `external` \| `generated` \| null |
| mobility | `fixed` \| `mobile` \| `stock` (see below) |
| category_id | Nullable FK → Category |
| tags | JSON array of strings |
| purchased_by_user_id | Nullable FK → User. Set at creation, never changes. "Who to ask." |
| vendor | Nullable text |
| purchase_date | Nullable date (separate from created_at — gear may be entered long after purchase) |
| order_url | Nullable text |
| created_by_user_id | FK → User |
| created_at, updated_at | UTCDateTime |

**mobility = fixed** — a room, shelf, wall-mounted pegboard. Cannot be
checked out. Just a node in the location tree. Can have a scan tag (scan
the shelf to see what's on it).

**mobility = mobile** — a toolbox, multimeter, torque wrench. Can be checked
out. Its "home" is its `parent_id` in the tree. Has checkout state columns:
`current_holder_id` (nullable FK → User), `checked_out_at` (nullable
UTCDateTime), `checkout_context` (nullable text — free-form snapshot of why,
e.g. "Suspension team — wheel bearing job").

**mobility = stock** — resistors, screws, heatshrink. Managed by quantity
rather than identity. Has stock columns: `stock_mode` (`exact` \| `fuzzy`),
`quantity` (nullable int), `low_stock_threshold` (nullable int),
`fuzzy_state` (nullable — small enum: `plentiful` \| `low` \| `empty`).

### Supporting tables

**Team** — id, name, description. Universal owning entity. Home deployment
= a team of one (or a household). Club deployment = a dozen+ specialist
teams. UI label configurable: "Team" for club, "Project" for home — this
distinction is purely a frontend label, the backend always calls it "team."

**Fixme: users can belong to multiple teams**
**TeamMembership** — user_id, team_id. Current membership only (no history,
no start/end dates). Each user has at most one current team. Self-editable
via the profile endpoint. Purpose: default pre-fill for `checkout_context`
when checking something out. Fully overrideable at checkout time (a student
helping another team can check out on behalf of that team).

**ThingImage** *(replaces single image_path field)* — id, thing_id,
image_path, is_primary (bool), uploaded_at, uploaded_by_user_id. Exactly
one image per thing may have `is_primary = true`. Setting a new primary
unsets the old one (like refresh token rotation). Served via the same
authenticated endpoint pattern as the current image serving endpoint.

**CheckoutLog** — id, thing_id, holder_id, checkout_context (text snapshot),
checked_out_at, checked_in_at (nullable = still out). Lightweight history
answering "who had this and when." Not forensic audit quality — just enough
to find out who last had the broken multimeter.

**StockAdjustment** *(evolution of AssetTransaction)* — id, thing_id, delta,
quantity_after, user_id, note, created_at. Kept for exact-mode stock items
only. Direct quantity mutation (no log) for fuzzy-mode items.

**Category** — unchanged from existing Phase 2. Any authenticated user can
manage categories.

**AuditLog** — unchanged from existing Phase 2. Admin/superuser only.
Records who created/updated/deleted entity records. Orthogonal to the
item-level checkout/stock history.

### Location model

No special "top-level location" vs "sub-location" distinction. All locations
are just `Thing` rows with `mobility = fixed` and a `parent_id`. Arbitrary
depth — rooms contain shelves contain toolboxes contain drawers, all as
sibling rows with parent-child links.

**Key property:** moving a container (e.g. toolbox 3 moves from shelf 4 to
under the workbench) means updating only one row (`toolbox3.parent_id`).
All items homed inside it automatically reflect the new location because
they reference the toolbox row, not the shelf row. No cascading updates.

**Privacy is dropped entirely.** All locations and items are visible to all
authenticated users. No `is_private` field, no cascade logic, no opaque 404s.

**Responsible team cascades** from the nearest ancestor with one set. Any
node can override it. Resolved by walking the ancestor chain at read time —
never cached or denormalised. At Bitza's scale (a few dozen locations) this
is trivially fast.

### Workshop manager

Resolved as just another team. Create a "Workshop" team (or "Workshop
Manager" team) with the relevant people as members. Items with no
`responsible_team_id` are considered to fall under whoever manages the
workshop team. No special boolean flag, no special entity. The CLI and admin
UI can label this appropriately.

### Scan interactions

Both locations and items have `scan_tag`. A scan resolves to a single
`GET /things/by-tag/{scan_tag}` endpoint returning the thing, its direct
children (if it's a location), and its current state (checked out / at home
/ stock level). The Angular UI decides what to show based on `mobility` and
whether the item is currently checked out.

Common flows:
- **Scan a location** → see what's directly there; option to drill into children
- **Scan a mobile item** → see if it's available or with someone; one-tap
  checkout ("I have this") or return ("returning to home")
- **"I found this"** → scan item → return to home → clears current holder

---

## What's still open / not yet decided

- **Multiple team memberships simultaneously** — parked, not decided. Current
  design assumes one active team per user. Revisit if the club deployment
  needs it.
- **QR code generation** — `tag_source = generated` implies the backend can
  generate a printable QR code label. Implementation not yet designed (format,
  print workflow, label template, etc.).
- **Low stock alerts** — `low_stock_threshold` is in the schema but no
  notification mechanism has been designed.
- **The Angular frontend** — not started. See `bitza_project_context.md`
  for the API contract details that the frontend will consume.

---

## The migration plan (not yet executed)

Phase 2 is a clean rebuild, not an incremental migration, because:
- No real production data exists yet (the superuser and a handful of test
  records at most)
- The schema change is fundamental (two tables → one unified table)
- The existing Phase 2 migration (`0002_assets.py`) can simply be replaced

Plan:
1. Delete all existing Phase 2 Python files (models, schemas, repos,
   services, endpoints)
2. Write new Phase 2 files implementing the Thing/Team/etc. model above
3. Replace `alembic/versions/0002_assets.py` with a new migration for the
   new schema
4. Update `alembic/env.py` and `tests/conftest.py` to import new models
5. Update `app/api/v1/router.py` to mount new endpoints
6. Write new tests for Phase 2

**Phase 1 (auth/users) is entirely untouched by all of this.**

---

## Key files to upload to a new chat

In order of importance:
1. This document (bitza_context_restoration.md)
2. `fastapi_sqlite_context_instructions.md` — general architectural rules
3. `bitza_project_context.md` — API contract, Angular notes, image serving
4. `assetmgmt.zip` — the current codebase (Phase 1 solid, Phase 2 to be replaced)

---

## First task for the new chat

Implement the new Phase 2 schema as described above. Suggested approach:

Start by confirming the full file list of what needs to be created and what
needs to be deleted before writing any code, to avoid confusion between old
and new Phase 2 files coexisting in the working copy.
