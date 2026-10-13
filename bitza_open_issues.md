# Bitza — open issues

**Status: Stage 6 is complete.** Backend `Team` → `Project` rename shipped
across two reviewed patches (backend, then frontend — see the "Stage 6
(complete)" section below for what was actually decided and delivered).
**Stage 7 is in progress** — see the "Stage 7" section below (document
attachments; backend done including upload file-type checking, frontend
deferred). For full project orientation start at
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

## Stage 7 — document attachments (datasheets / SDS) — backend done

**Goal:** attach a data/spec sheet or SDS/MSDS (mostly PDF) to a bitza —
chiefly stock items such as electronic components — so real data can start
going in.

**Decided:** metadata all optional (including the original URL); files on the
filesystem with the path in the DB, as for images; DB/filesystem sync is a
later admin-side process; backend first, frontend later; upload file-type
sanity checking is separate work (since done, see below). Full contract in
`bitza_project_context.md` ("Documents").

**Backend delivered:** migration `0005_bitza_documents`, `BitzaDocument` model,
`BitzaDocumentRepository`, upload/list/download/PATCH/delete in
`BitzaService` + five endpoints, `MAX_DOCUMENT_BYTES` setting,
`tests/test_documents.py`. 212 backend tests green (166 + 46 new); the
migration was checked with `alembic check` (no drift) and a downgrade/upgrade
round-trip.

**File-type checking delivered (backend):** `app/core/file_types.py` sniffs
every document upload from its leading bytes (ZIP containers by member names)
against a strict allow-list — PDF, PNG, JPEG, GIF, WebP, ZIP, OOXML,
OpenDocument, UTF-8 plain text. Anything else is a 415. The client's
`Content-Type` and extension are ignored; the *detected* type is stored,
served on download (anything off the allow-list is served as
`application/octet-stream`) and used for the on-disk extension. Uploads stream
to a `.part` file and are renamed once classified. 286 backend tests green
(212 + 74 new: `tests/test_file_types.py` plus a content-sniffing section in
`tests/test_documents.py`). Details in `bitza_project_context.md`
("Documents"). Image uploads got the same check in a follow-up patch (see
below). Not done: whole-file validation or malware scanning.

**Image upload check delivered (backend):** image uploads are now sniffed with
the same module (`detect_image_type`: JPEG, PNG, GIF, WebP; SVG deliberately
not accepted). The client's `Content-Type` and extension are ignored, the
on-disk extension follows the content, unsupported content is a **415**
(previously a 422 based on the claimed type only), and image serving adds
`nosniff` and maps any non-image extension (pre-existing files) to
`application/octet-stream`. `tests/test_images.py` is new — the image
endpoints had no backend tests before. 332 backend tests green (286 + 46). Also fixed: the image 413 path used a
deprecated Starlette constant that errors under `-W error`.

**Still to do for Stage 7:**
- **Frontend**: model, service, and a documents section on the bitza detail
  page (upload, list, download via blob fetch — saved as a download, never
  opened inline in the app — edit metadata, delete). Avoid
  the visually-hidden-input pattern the image gallery uses for the new
  upload control (axe has never been run on it).
- **DB↔filesystem sync tooling** for admins (orphaned files, missing files;
  the stored `sha256` allows integrity checks).
- Known related gaps: image files are not removed when a bitza is hard
  deleted; documents/images live in the same volume as the DB but the
  documented backup copies only the `.db` file.

---

## Backlog (not scheduled)

The backlog items below are scattered
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
