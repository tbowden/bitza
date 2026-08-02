# Bitza — open issues

**Status: Stage 5 is complete.** All four items below were fixed, tested,
applied, and pushed across four reviewed patches. This document now
tracks **Stage 6**, the next planned work. For full project orientation
start at `bitza_context_restoration.md`; for the backend architecture
these items touch, see `bitza_project_context.md`.

---

## Stage 5 (complete) — post-reconciliation fixes

Kept brief on purpose — the blow-by-blow has been dropped; see
`bitza_context_restoration.md`'s "Lessons learned" section for what's
still worth carrying forward (the guards-don't-protect-siblings lesson in
particular came directly out of this stage).

1. **Login now lands on `/me`**, not `/bitzas` — a one-line default-route
   fix (`app.routes.ts`).
2. **Root bitza locked down** — `PATCH` accepts `name` only, admin/
   superuser only; `reassign-team` blocked on it unconditionally too
   (found while implementing, not in the original ask). See
   `bitza_project_context.md`'s Hierarchy section.
3. **Stock bitzas can't have children** — enforced on create, on move,
   and on the kind transition itself. See `bitza_project_context.md`'s
   `kind` section.
4. **Team → Project, frontend** — `AppConfigService` and its toggle
   removed; UI always says "Project"/"Projects" now. See
   `bitza_project_context.md`'s "Teams" section.

---

## Stage 6 (next, not started) — Team → Project, backend

**Not yet scoped — needs a discussion before any patches get cut.** This
reverses what `bitza_project_context.md` used to say ("the database and
API stay named `Team` — never in question"); that section has already
been updated to reflect the reversal. The frontend-only pass (Stage 5,
item 4 above) is done; this is the equivalent move for everything Stage 5
deliberately left alone.

**What's known to be involved, at minimum** (informational, not a
commitment to this exact scope — flagging so a scoping conversation has
somewhere to start):

- `models/team.py` — the SQLAlchemy model and its table name.
- An Alembic migration to actually rename the table/columns (`teams`,
  `team_id` FKs across `bitzas`, `team_members`, `checkouts`'
  `team_context` is free-text so likely untouched — worth confirming).
- `schemas/team.py` — `Team`/`TeamCreate`/`TeamRead`/`TeamListRead`/
  `TeamMemberRead` and friends.
- `repositories/team_repository.py`, `services/team_service.py`.
- `api/v1/endpoints/teams.py` and the route prefix itself
  (`/api/v1/teams/` → presumably `/api/v1/projects/`).
- Backend tests (`tests/test_teams.py` and any cross-references in
  `test_bitzas.py`).
- The frontend's own `Team`-named identifiers that Stage 5 deliberately
  left alone — models, services, route paths (`/teams`), component/class/
  file names (`TeamsList`, `team-detail.ts`, etc.) — since the frontend
  was scoped as display-labels-only last time, all of this still says
  `Team` today and would need revisiting if the backend rename lands.

**Open questions worth settling before starting, not during:**
- Does the route path change (`/teams` → `/projects`) at the same time,
  or does the backend rename land first with routes following later?
  A route change is more disruptive than a table rename (bookmarks,
  any external integrations) and may warrant its own decision.
- Same question for the frontend's internal naming (files/classes/CSS) —
  worth doing as part of this, or a separate future pass? Stage 5 treated
  this as explicitly out of scope; that call is worth revisiting now that
  the backend is following, not just the display text.
- Migration strategy for existing deployments (rename in place vs.
  additive-then-cutover) — depends on whether this project has any real
  deployments with data yet worth worrying about.

Once scoped, this should get the same treatment as Stage 5: divided into
reviewable chunks (backend first, frontend second, matching how Stage 5
was run), one patch file per chunk, applied one at a time.
