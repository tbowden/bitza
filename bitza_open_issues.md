# Bitza — open issues

**Status: Stage 6 is complete.** Backend `Team` → `Project` rename shipped
across two reviewed patches (backend, then frontend — see the "Stage 6
(complete)" section below for what was actually decided and delivered).
**No Stage 7 is scoped yet.** For full project orientation start at
`bitza_context_restoration.md`; for the backend architecture these items
touch, see `bitza_project_context.md`.

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

## Stage 6 (complete) — Team → Project, backend

Scoped via a short round of questions, then delivered as two reviewed
patches (backend, then frontend), each verified against a fresh clone
with its full test suite green before being applied.

**Scoping decisions made:**
- Route paths renamed in the same pass — `/api/v1/teams/` →
  `/api/v1/projects/`, including `/reassign-team` → `/reassign-project`.
- Frontend internals renamed in the same pass too — files, classes,
  routes, models. Nothing was left saying `Team` anywhere, backend or
  frontend.
- Migration done as a straightforward in-place rename, not
  additive-then-cutover — no production deployments existed yet.

**What actually changed:**
- `models/team.py` → `models/project.py`, `schemas/team.py` →
  `schemas/project.py`, `repositories/team_repository.py` →
  `repositories/project_repository.py`, `services/team_service.py` →
  `services/project_service.py`, `api/v1/endpoints/teams.py` →
  `api/v1/endpoints/projects.py`, plus every cross-referencing file
  (`bitza` model/schema/repository/service, `user` schema/service,
  `audit`, `dependencies.py`, `router.py`, `cli.py`).
- New Alembic migration renaming `teams`→`projects`,
  `team_members`→`project_members` (incl. its `team_id`→`project_id`
  column and unique constraint), `bitzas.responsible_team_id`→
  `responsible_project_id`, and `checkouts.team_context`→
  `project_context` (the one field flagged as "worth confirming" — it
  got renamed too, for full consistency, since the whole-stack rename
  was in scope).
- Frontend: `features/teams/` → `features/projects/`
  (`teams-list`→`projects-list`, `team-detail`→`project-detail`,
  `team-form-dialog`→`project-form-dialog`), `reassign-team-dialog` →
  `reassign-project-dialog`, `team.model.ts`/`team.service.ts` →
  `project.model.ts`/`project.service.ts`, and every route/routerLink
  cross-reference.
- 166 backend tests / 42 frontend tests, all still green.

**Known follow-up, not yet done:**
- None — the tutorial doc (`backend/docs/ARCHITECTURAL_OVERVIEW.md`) and
  all three context docs (`bitza_project_context.md`,
  `bitza_frontend_context.md`, `bitza_context_restoration.md`) have been
  swept for stale `team`/`Team` references and brought in line with the
  Stage 6 rename as a same-day follow-up (docs-only, no code changes).

---

## Stage 7 — not yet defined

Nothing is scoped here yet. The backlog items below are scattered
mentions from the other context docs (`bitza_frontend_context.md`'s
"Deliberately out of scope / deferred" section, `bitza_project_context.md`'s
"Still genuinely open" note) — informational, not a commitment to any of
this being next:

- **Accessibility**: no automated tooling has ever been run (no axe-core,
  no Lighthouse pass), no keyboard-only walkthrough, no screen reader
  spot-check. Fixes so far were found by manually reading Material's
  compiled source, not a systematic scan.
- **No component-level or e2e tests** — the 42 frontend tests are all
  service-layer (`HttpTestingController`), nothing exercises a
  component's template or rendered output.
- **Milestone 1–4 inline-template retrofit** — those components predate
  the Stage 5-onward external-template convention and haven't been
  converted.
- **Cross-bitza dashboards** — low-stock alerts and a club-wide "recent
  activity" feed were explicitly left undecided, not just unbuilt (the
  `/me` page's personal "what's checked out" view is the only piece
  that exists).
- **Comp/trip packing lists** — no backend support exists; not built.
- **In-app barcode/serial scanner** (camera-based) — deferred; QR
  route/label scanning is the supported mechanism today.
- **Image thumbnails in list/table views** — scope cut to avoid an
  authenticated-blob-fetch-per-row cost.
- **Offline behaviour** — out of scope for now; the SQLite backend has
  no sync capability.
