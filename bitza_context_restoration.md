# Bitza — context restoration

**Purpose of this document:** this is the "start here" briefing for a new
chat picking up work on Bitza. It tells you what stage the project is at,
where to find the detailed design/API contract, and what's expected next.
It is deliberately short — for the full domain model and API shapes, see
**`bitza_project_context.md`**; for everything about the Angular frontend
specifically (architecture, conventions, what's built, known gaps), see
**`bitza_frontend_context.md`**. Read both before writing any frontend
code. This file just orients you and tells you which of those two to reach
for.

If you are a fresh Claude instance reading this for the first time:
welcome. Read this file, then `bitza_project_context.md`, then
`bitza_frontend_context.md` before doing anything else.

---

## What Bitza is (one paragraph)

A tracker for physical stuff — originally home workshop components and
tools, now generalised to also serve community or student clubs with
rotating membership and multiple potentially overlaping teams or projects.
One unified data model serves both; the club case is simply the richer end
of the same schema. Backend: FastAPI + SQLite. Frontend: Angular 22 +
Angular Material.

---

## Stage tracker

| Stage | Scope | Status |
|---|---|---|
| **1** | Auth, users, roles (superuser/admin/user), JWT refresh/rotation, password policy | ✅ Done, tested, untouched since |
| **2** | Unified `Team`/`Bitza` backend model | ✅ Done, tested |
| **3** | Angular frontend | ✅ All 5 planned milestones built (Foundation, Teams, Bitzas core, Bitza actions, Admin & polish) — see caveats below |
| **4** | Frontend/backend schema reconciliation, completeness pass, `/me` landing page, `kind` editability | ✅ Done. The dedicated doc this was tracked in has been retired — durable lessons folded into this file below; current behavior is described directly in `bitza_project_context.md`/`bitza_frontend_context.md` |
| **5** | Post-reconciliation fixes (login→`/me` default, root bitza lockdown, stock-can't-have-children, Team→Project frontend rename) | ✅ Done — four items, applied and pushed across four reviewed patches |
| **6** | Team → Project, backend | 🔲 Planned, not started, not yet scoped — see `bitza_open_issues.md` |

**Testing methodology — read this before assuming anything is "confirmed working":**
For most of this project's life there was **zero live click-through** —
everything was verified via `pytest`/`ng build`/`ng test` plus careful
source reading, with no browser ever pointed at a real running backend.
**That has changed as of Stage 5**: the project owner is now running the
frontend against a live backend directly and using that to decide what
needs fixing — this is how Stage 5's four issues were found, and how
future issues will keep surfacing. It's real verification but not
exhaustive or complete — no formal QA pass, no systematic click-through
of every screen, no automated e2e or axe audit, work in progress rather
than finished. Treat "hasn't been reported as broken" as weaker evidence
than "confirmed working," and expect new issues to arrive this way —
from the owner's own manual testing — rather than from further code
review turning them up.

**Still true, and still worth knowing:**
- **No component-level tests exist** — only `core/services/*.spec.ts`
  (HTTP contract tests via `HttpTestingController`) plus one guard spec.
  42 tests across 11 files as of Stage 5. No component specs, no e2e.
- **No automated accessibility audit (axe or similar) has ever been
  run.** A number of real accessibility bugs were found and fixed by
  manually reading Material's compiled source (not by running a
  checker) — see `bitza_frontend_context.md` for specifics. Treat the
  current state as "meaningfully better than default, not verified
  compliant."
- **Component templates/styles are inconsistent.** Milestones 1–4 use
  inline `template`/`styles`; Milestone 5 onward uses external
  `.html`/`.scss` files, the stated convention going forward (see
  `frontend/bitza/.claude/CLAUDE.md`). Retrofitting 1–4 to match is
  known, deliberate, outstanding work — the project owner said they'd
  handle it rather than have Claude do it as a bulk pass.

Stage 2 was a full rebuild, not an incremental migration — there was no
production data, so the old location/asset tables and endpoints were
deleted outright rather than migrated. See `MIGRATION_NOTES.md` (backend
root) if anything about the old shape ever needs to be dug up from history.

---

## Lessons learned (condensed from now-retired historical docs)

Stage 4's schema-reconciliation pass (16 patches) and Stage 5's four-item
pass both had their own play-by-play tracking documents at the time;
those have been dropped now that the work is done — full history is
still in `git log` if it's ever needed. What's durably useful from both,
kept here rather than in a file about to go stale again:

- **Frontend/backend field drift is a real, recurring bug class in this
  project, not a one-off.** Five features were confirmed completely
  non-functional purely from field-name/polarity mismatches between the
  frontend's guessed models and the backend's actual Pydantic schemas
  (create-user, suspend/unsuspend, checkout holder, team member names,
  audit summaries) — found by reading `backend/app/schemas/*.py`
  directly against `frontend/.../core/models/*.ts`, not by reproducing a
  failure. When adding or touching a frontend model, verify field names
  and polarity against the live schema file, not against prose in these
  docs.
- **List-response types and detail-response types are genuinely
  different shapes here** — list endpoints deliberately send less data
  than detail endpoints. Using one TypeScript type for both silently
  drops fields the list endpoint never sent. This caused two real, live
  bugs (blank stock quantities and blank team descriptions in grid/table
  views) before the types were properly split.
- **Adding a guard to one code path doesn't protect its siblings.**
  Stage 5's root-bitza lockdown (PATCH-only, name-only, admin-only)
  initially missed that `reassign-team` changes the same field through a
  separate endpoint; the move-bitza destination picker likewise had no
  defense against picking a stock bitza as a target. Both were found and
  closed while implementing the primary ask, not from a bug report. When
  adding a business-rule guard, deliberately check for other mutating
  endpoints or UI flows that touch the same field/rule before calling it
  done.
- **Milestone delivery-by-overlay silently drops file changes and
  deletions.** Early on, an entire milestone's worth of components
  (`CheckoutSection`, `StockSection`, `ImageGallery`) existed as
  complete, correct files that were never actually wired into
  `bitza-browser.ts` — nothing imported or rendered them — because
  milestones were incorporated by overlaying new/changed files onto the
  existing tree rather than a clean replace, which silently drops
  changes to files that already existed (and can't remove a file a new
  version deleted). Confirmed via git history showing the wiring file
  untouched since the prior milestone. Prefer a clean replace of a whole
  source tree over a selective file-by-file overlay when incorporating
  bulk work, or diff carefully against git history afterward.
- **The Angular CLI's own Node-version gate can be worked around locally
  for verification only** — patch `isNodeVersionSupported`/
  `isNodeVersionMinSupported` in
  `node_modules/@angular/cli/src/utilities/node-version.js` to return
  `true`, never commit it (`node_modules` is gitignored) — when a
  sandbox's Node patch version trails the CLI's floor
  (`^22.22.3 || ^24.15.0 || >=26.0.0`) but is otherwise close enough to
  build/test correctly.
- **How work has been getting done, as a process note for whoever picks
  this up next:** the owner tests manually, reports what's broken or
  wanted, changes get scoped into small reviewable chunks (backend
  first, then frontend, when both are involved), one patch file per
  chunk verified against a clean clone before handing it over, applied
  and pushed one at a time rather than all at once. Stage 5 ran this way
  end to end and it worked well — worth continuing for Stage 6.

---

## Repo structure

```
bitza/
├── README.md
├── bitza_project_context.md         ← full backend design doc, API contract
├── bitza_context_restoration.md     ← this file
├── bitza_frontend_context.md        ← full frontend design doc — READ THIS for any frontend work
├── bitza_open_issues.md             ← active/next task: Stage 6 (Team→Project backend rename)
├── backend/
│   ├── AI_instructions.md
│   ├── ARCHITECTURAL_OVERVIEW.md
│   ├── DEPLOYMENT.md
│   ├── MIGRATION_NOTES.md
│   ├── .gitignore                   ← Python/uv-specific rules only
│   ├── app/            models/, schemas/, repositories/, services/, api/v1/endpoints/, core/
│   ├── alembic/versions/
│   └── tests/
└── frontend/
    ├── .nvmrc                        ← v24.16.0
    └── bitza/                        ← the actual Angular project (npm root)
        ├── .claude/CLAUDE.md         ← Angular/TS conventions Claude follows in this project
        ├── .gitignore                ← Angular/Node-specific rules only
        ├── package.json / package-lock.json  ← lockfile IS committed, deliberately
        ├── angular.json
        └── src/app/
            ├── core/
            │   ├── models/           one file per API entity + index.ts barrel
            │   ├── services/         one per resource, @Service() decorator, HttpClient-based
            │   ├── interceptors/     auth.interceptor.ts (401 → refresh → retry)
            │   └── guards/           auth.guard.ts, admin.guard.ts, redirect-to-root.guard.ts
            ├── shared/
            │   └── confirm-dialog/   reusable destructive-action confirmation
            ├── shell/
            │   └── app-shell.ts      toolbar + responsive sidenav + skip link
            └── features/
                ├── auth/login/
                ├── teams/            list, detail, form dialog, add-member dialog
                ├── bitzas/           browser (tree nav), form/retire/reassign/move dialogs,
                │                     checkout/stock/image sections + their dialogs,
                │                     category manager
                ├── me/               personal landing page (checked-out items, your teams) — the default route
                ├── users/            admin-only list + form dialog
                └── audit/            admin-only log view
```

The top-level `.gitignore` was deliberately split three ways (root =
editors/OS only, `backend/.gitignore` = Python/uv,
`frontend/bitza/.gitignore` = Node/Angular) — general rules cascade down
from root automatically, so the per-stack files only need what's actually
specific to that stack. `package-lock.json` is committed on purpose.

---

## The API surface, condensed

See `bitza_project_context.md` for the full contract. The frontend
implements essentially all of it: auth (login/refresh/logout with
rotational tokens), teams + membership (including `/teams/mine`), the
full bitza tree model (create/edit/retire/reactivate/reassign-team,
root-bitza lockdown, stock-can't-have-children), checkout/checkin
(including `/checkouts/mine`), stock adjustments, images (authenticated
blob fetch), categories, users (admin), and the audit log.

---

## How to get further detail without re-deriving it

- **Full backend domain model, every schema/endpoint shape, and the
  reasoning behind each design decision** → `bitza_project_context.md`
- **Active task: Team → Project backend rename, not yet scoped** →
  `bitza_open_issues.md`
- **Full frontend architecture: what's built, conventions, Signal Forms
  usage notes, known assumptions needing backend confirmation, testing
  state, and outstanding work** → `bitza_frontend_context.md`
- **General FastAPI/SQLAlchemy/uv conventions the backend follows** →
  `backend/AI_instructions.md`
- **Angular/TypeScript conventions Claude follows in the frontend
  project** → `frontend/bitza/.claude/CLAUDE.md`
- **What got deleted/replaced during the Stage 2 backend rebuild** →
  `backend/MIGRATION_NOTES.md`
