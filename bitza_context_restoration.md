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
`bitza_frontend_context.md` before doing anything else — the frontend has
accumulated real architecture and a handful of documented-but-unconfirmed
assumptions that matter before you touch it.

---

## What Bitza is (one paragraph)

A tracker for physical stuff — originally home workshop components and
tools, now generalised to also serve community or student clubs with
rotating membership and multiple potentially overlaping teams or projects. 
One unified data model serves both; the club case is simply the richer end of 
the same schema. Backend: FastAPI + SQLite. Frontend: Angular 22 + Angular Material.

---

## Stage tracker

| Stage | Scope | Status |
|---|---|---|
| **1** | Auth, users, roles (superuser/admin/user), JWT refresh/rotation, password policy | ✅ Done, tested, untouched since |
| **2** | Unified `Team`/`Bitza` backend model | ✅ Done, tested (58/58 passing) |
| **3** | Angular frontend | 🟡 All 5 planned milestones built (Foundation, Teams, Bitzas core, Bitza actions, Admin & polish) — see caveats below; the frontend/backend schema-drift caveat that used to be here is now resolved (see Stage 4) |
| **4** | Frontend/backend schema reconciliation + completeness pass | ✅ Done — 16 patches (`bitza_schema_reconciliation_todo.md`), applied and pushed. Both design questions that came out of it — a personal `/me` landing page, `kind` editability/labelling — are also done, tested, applied, and pushed. That doc is now a fully historical record; nothing in it is outstanding |
| **5** | Post-reconciliation fixes | 🔲 Not started — four items, see `bitza_open_issues.md`: login should land on `/me` (a gap in Stage 4's own routing plan that didn't ship), root bitza needs locking down to name-only/admin-only, stock bitzas shouldn't be able to have children, and the Team/Project naming question is now decided ("Project") but not yet implemented |

**Stage 3 caveats — read before continuing frontend work:**

- **This has not had a live QA / click-through pass.** Everything has been
  verified via `ng build` and `ng test` (35 passing unit tests at Stage 3's
  original completion, grown to 42 since — see `bitza_frontend_context.md`'s
  Testing state section for the current count, all still at the
  service layer) in a sandboxed environment with no real backend to talk
  to and no browser to actually click through. Nothing has been visually
  confirmed to render or behave correctly against a live API.
- **No component-level tests exist yet** — only `core/services/*.spec.ts`
  (HTTP contract tests via `HttpTestingController`). No component specs,
  no e2e.
- **No automated accessibility audit (axe or similar) has been run.**
  A number of real accessibility bugs were found and fixed by manually
  reading Material's compiled source (not by running a checker) — see
  `bitza_frontend_context.md` for specifics. Treat the current state as
  "meaningfully better than default, not verified compliant."
- **The frontend's data models had confirmed drift from the real backend
  schemas, breaking several already-shipped features — this is now
  resolved (Stage 4 above).** Found by reading `backend/app/schemas/*.py`
  directly, not by observing a failure (this project still has never had
  a live click-through against a running backend). Creating a user,
  suspend/unsuspend, checkout holder display, team member names, and
  audit log summaries were all confirmed non-functional due to
  field-name or polarity mismatches, plus two more live bugs found
  during the completeness pass (exact-mode stock quantities and team
  descriptions both silently failing to display). All fixed — 16
  patches, see `bitza_schema_reconciliation_todo.md` for the full
  history. The `GET /api/v1/users/` permission question is resolved too
  (it's genuinely admin-gated; fixed via a new, narrower
  `/users/directory` endpoint rather than relaxing that gate).
  **The two design questions that came out of this work — a personal
  `/me` landing page, and `kind` editability/labelling — are also both
  now done, tested, applied, and pushed.** See that same doc's "New
  design questions raised" section for what shipped, and
  `bitza_open_issues.md` for four new items that came out of finishing
  this stage (Stage 5 above).
- **Component templates/styles are inconsistent.** Milestones 1–4 use
  inline `template`/`styles`; Milestone 5 (Users, Audit) uses external
  `.html`/`.scss` files, which is now the stated convention going forward
  (see `frontend/bitza/.claude/CLAUDE.md`). Retrofitting 1–4 to match is
  known, deliberate, outstanding work — the project owner said they'd
  handle it rather than have Claude do it as a bulk pass.
- **A real bug was found and fixed mid-Stage-3 that's worth knowing
  about as a process lesson, not just a code fix:** partway through, an
  entire milestone's worth of components (`CheckoutSection`,
  `StockSection`, `ImageGallery` — the Milestone 4 "Bitza actions" work)
  existed as complete, correct files that were **never actually wired
  into `bitza-browser.ts`** — nothing imported or rendered them, so none
  of that milestone's functionality was reachable in the running app
  despite the files being present and the milestone having been announced
  as "done." Git confirmed `bitza-browser.ts` hadn't been touched since
  the prior milestone's commit. This happened because each milestone was
  delivered as a full zip of the frontend project, but incorporating it
  into the real repo was apparently done by overlaying new/changed files
  onto the existing tree rather than a clean replace — which silently
  drops changes to files that already existed. **This has been fixed**
  (bitza-browser.ts now correctly imports and renders all three), but the
  underlying process risk remains: if milestones get incorporated the
  same way again, the same class of silent gap can recur. Prefer a clean
  replace of the whole `frontend/bitza/src/` tree over a selective
  file-by-file overlay when incorporating future work, or diff carefully
  against git history afterward.

Stage 2 was a full rebuild, not an incremental migration — there was no
production data, so the old location/asset tables and endpoints were
deleted outright rather than migrated. See `MIGRATION_NOTES.md` (backend
root) if anything about the old shape ever needs to be dug up from history.

---

## Repo structure (as of end of Stage 3, Milestone 5)

```
bitza/
├── README.md
├── bitza_project_context.md         ← full backend design doc, API contract
├── bitza_context_restoration.md     ← this file
├── bitza_frontend_context.md        ← full frontend design doc — READ THIS for any frontend work
├── bitza_schema_reconciliation_todo.md  ← historical record, fully done — read bitza_open_issues.md instead
├── bitza_open_issues.md             ← active task: four new items post-reconciliation, fix these next
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
                ├── bitzas/           browser (tree nav), form/retire/reassign dialogs,
                │                     checkout/stock/image sections + their dialogs,
                │                     category manager
                ├── me/               personal landing page (checked-out items, your teams)
                ├── users/            admin-only list + form dialog
                └── audit/            admin-only log view
```

The top-level `.gitignore` was deliberately split three ways during Stage
3 (root = editors/OS only, `backend/.gitignore` = Python/uv,
`frontend/bitza/.gitignore` = Node/Angular) — general rules cascade down
from root automatically, so the per-stack files only need what's actually
specific to that stack. `package-lock.json` is committed on purpose; it
wasn't for a while early on due to a stale gitignore rule someone had
copied from elsewhere, which has since been corrected.

---

## The API surface, condensed

Unchanged from before — see `bitza_project_context.md` for the full
contract. The frontend now implements essentially all of it: auth
(login/refresh/logout with rotational tokens), teams + membership, the
full bitza tree model (create/edit/retire/reactivate/reassign-team),
checkout/checkin, stock adjustments, images (authenticated blob fetch),
categories, users (admin), and the audit log.

---

## How to get further detail without re-deriving it

- **Full backend domain model, every schema/endpoint shape, and the
  reasoning behind each design decision** → `bitza_project_context.md`
- **Active task: four items to fix next** (login should land on `/me`,
  root bitza needs locking down to name-only/admin-only, stock bitzas
  shouldn't be able to have children, Team/Project naming decided but not
  yet implemented) → `bitza_open_issues.md`
- **Historical record of the frontend/backend field-drift fix and the
  two design questions it raised** (both now built) →
  `bitza_schema_reconciliation_todo.md` — nothing left to do here, but
  useful context for *why* things are shaped the way they are
- **Full frontend architecture: what's built, conventions, Signal Forms
  usage notes, known assumptions needing backend confirmation, testing
  state, and outstanding work** → `bitza_frontend_context.md`
- **General FastAPI/SQLAlchemy/uv conventions the backend follows** →
  `backend/AI_instructions.md`
- **Angular/TypeScript conventions Claude follows in the frontend
  project** → `frontend/bitza/.claude/CLAUDE.md`
- **What got deleted/replaced during the Stage 2 backend rebuild** →
  `backend/MIGRATION_NOTES.md`
