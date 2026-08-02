# Bitza — frontend context

Full detail on the Angular frontend built during Stage 3: architecture,
conventions, what's implemented, what's assumed vs. confirmed, and what's
still owed. Read `bitza_context_restoration.md` first for orientation and
`bitza_project_context.md` for the backend/API contract this all sits on
top of. This document is frontend-only.

---

## Stack and setup

- **Angular 22**, standalone components throughout, no NgModules.
- **Angular Material 22 + CDK**, installed manually rather than via
  `ng add` — the schematic refuses to run under a Node version below its
  engine floor (`^22.22.3 || ^24.15.0 || >=26.0.0`). If you ever need to
  add another Material-adjacent package the same way: install the npm
  packages directly, wire up the theme in `styles.scss` by hand, no
  schematic needed.
- **`@angular/animations` was deliberately removed.** Material 22's own
  components (menu, sidenav, expansion, dialog, snack-bar, etc.) animate
  via native CSS internally now and don't need it — confirmed by grepping
  the compiled Material bundles for imports from `@angular/animations`
  (zero hits across every module actually used here). The only thing that
  had pulled the package in was our own call to the now-deprecated
  `provideAnimationsAsync()`, which was removed along with the
  dependency. If a future dependency genuinely needs the old
  trigger/state/transition animation DSL, reach for `animate.enter`/
  `animate.leave` (the native replacement) rather than reinstalling the
  deprecated package.
- **`qrcode` (npm, MIT)** — generates the QR label shown on a bitza's
  detail page client-side. Named exports (`import { toDataURL } from
  'qrcode'`), not a default export.
- **Signal Forms** (`@angular/forms/signals`) used for every form in the
  app, per the project's stated preference. This is a very new API with
  sparse documentation — see the dedicated section below before touching
  any form.
- **`@Service()` decorator** used instead of `@Injectable({providedIn:
  'root'})` for every singleton service, per
  `frontend/bitza/.claude/CLAUDE.md`. Confirmed this actually exists and
  works in Angular 22 before adopting it (it's a real, functioning
  shorthand — auto-registers in root, no config object).
- **Testing**: Angular's newer native `@angular/build:unit-test` builder
  (Vitest-based), not Karma. Runs headlessly via jsdom, no browser
  download needed.

### Design tokens

Grounded in the subject matter rather than a generic brand palette:

- **Color**: Material M3 theme, blue primary / orange tertiary — a
  workshop-signage-adjacent palette (steady technical blue, hazard-tape
  amber accent) rather than the cliché terracotta/cream or default-purple
  looks.
- **Type**: Inter for UI text, **IBM Plex Mono for anything that
  identifies a specific physical thing** — bitza IDs, category tags,
  timestamps — deliberately echoing the printed asset-tag/QR-label
  concept described in the backend docs. There's a `.bitza-tag` utility
  class in `styles.scss` for this.
- Both fonts loaded via Google Fonts `<link>` in `index.html`, alongside
  Material Symbols Outlined for `mat-icon` (configured as the default
  icon font set via `MAT_ICON_DEFAULT_OPTIONS` in `app.config.ts`).

---

## Architecture conventions

```
core/
  models/       one .ts file per API entity, plain interfaces/types, index.ts barrel export
  services/     one per resource (ProjectService, BitzaService, UserService, ...),
                thin HttpClient wrappers, @Service()-decorated, no business logic beyond
                the odd client-side default (e.g. cascade_scope UI defaults)
  interceptors/ auth.interceptor.ts only
  guards/       auth.guard.ts (any authenticated user), admin.guard.ts (admin/superuser)
shared/
  confirm-dialog/  the one cross-cutting reusable dialog (destructive-action confirmation)
shell/
  app-shell.ts     toolbar + responsive Material sidenav + skip-to-content link
features/
  <feature>/<component-name>/<component-name>.ts (+ .html + .scss from Milestone 5 on)
```

- **Routing**: lazy-loaded standalone components (`loadComponent`), guards
  applied per-route (`authGuard` on everything under the shell,
  `adminGuard` additionally on `/users` and `/audit`).
- **State**: signals throughout, no NgRx/service-level state stores.
  List/detail pages generally follow the same pattern — a `reload =
  signal(0)` bumped after a mutation, feeding a `combineLatest`-driven
  refetch via `toObservable`/`toSignal`. This is simple and has worked
  fine at this scale; it means every mutation triggers a full refetch of
  the current view rather than a targeted cache update. Worth revisiting
  if any list ever needs to handle real volume.
- **Dialogs over dedicated routes** for all create/edit/confirm flows
  (Material's `MatDialog`, CDK-based, proper focus trapping for free).
- **Team vs Project label**: settled as always "Project" (Stage 5) —
  `AppConfigService` and its runtime `localStorage`-persisted toggle were
  removed entirely rather than kept as a settings option, since the
  choice turned out to be permanent, not deployment-specific. Stage 6
  then carried that rename into the actual identifiers too — `Project`/
  `project_id`/etc. are now the real backend and TypeScript identifiers
  throughout (routes, class names, model fields), not just the rendered
  UI text. See `bitza_project_context.md`'s "Projects" section and
  `bitza_open_issues.md`'s Stage 6 entry for what that pass covered.
- **`cascade_scope` UI defaults** (reassign-project dialog): `fixed`/`stock`
  → `none`, `mobile` → `all_descendants`, always overridable. This is
  frontend-only convenience — the backend never infers or defaults this
  and always requires it explicitly, per the backend docs.
- **Authenticated image fetching**: there's no unauthenticated static
  path for bitza images, so `ImageGallery` fetches every file via
  `HttpClient` with `responseType: 'blob'` and builds object URLs,
  revoking them both on list changes and component destroy. Deliberately
  does **not** show thumbnails in any list/table view (would mean an
  authenticated blob fetch per row) — images are detail-view-only for now.
- **Root bitza and stock-can't-have-children guards, reflected client-side**
  (Stage 5, mirroring the backend rules in `bitza_project_context.md`'s
  Hierarchy/`kind` sections): `BitzaFormDialog` shows only the Name field
  (plus a note) when editing the root, and disables "Stock" in the Type
  dropdown when the bitza already has children; `BitzaBrowser` hides "Add
  here" for stock bitzas and "Edit"/"Reassign" for non-admins on the root;
  `MoveBitzaDialog` disables "Move here" while browsing into a stock
  location. All of these are UX conveniences on top of backend
  enforcement, not the enforcement itself — the backend rejects the same
  cases independently.

### Component file structure — inconsistent, on purpose (for now)

- **Milestones 1–4**: inline `template`/`styles` inside the `@Component`
  decorator.
- **Milestone 5 onward**: external `.html`/`.scss` files, per an explicit
  preference change partway through the build (now recorded in
  `frontend/bitza/.claude/CLAUDE.md`).
- Retrofitting 1–4 to match is known, outstanding work. The project owner
  said they'd handle this themselves rather than have it done as a bulk
  automated pass — don't do this unprompted.

---

## Signal Forms — API notes (read before touching any form)

This API (`@angular/forms/signals`) is new enough that its shape isn't
reliably in general training data. Everything below was confirmed by
reading the *compiled* package source directly
(`node_modules/@angular/forms/fesm2022/signals.mjs` and the
`.d.ts` files), not assumed from memory — worth doing again if the
Angular version bumps and something stops working.

- **`form(modelSignal, schemaFn?)`** returns a `FieldTree`. Bind a plain
  `WritableSignal<T>` holding the whole form's data shape.
- **Binding to inputs**: the `FormField` directive, selector `[formField]`
  (NOT `[field]` or `[control]` — those don't exist). Usage:
  `<input matInput [formField]="myForm.someProperty" />`. It interops
  with CVA-based Material controls (`mat-select`, etc.) via an internal
  `NgControl` bridge, confirmed working throughout this project (selects,
  checkboxes, button-toggles, textareas, native inputs).
  - **Do not** combine `[formField]` with a static HTML validation
    attribute like `min="1"` on the same element — the compiler
    explicitly rejects this (`NG8022`) since Signal Forms owns validation
    itself. Use the `min()`/`max()`/`required()` schema validators instead.
- **Validators**: `required(path, {message})`, `min(path, value,
  {message})`, `max()`, `pattern()`, all imported from
  `@angular/forms/signals`.
- **Conditional validation**: `applyWhen(path, (ctx) => boolean, (path) =>
  {...})` — used for kind-conditional bitza fields (stock_mode only
  required when kind === 'stock', fuzzy_state only when stock_mode ===
  'fuzzy') and for create-vs-edit conditional password requirement on the
  user form. Read sibling values inside the predicate via
  `ctx.valueOf(path.someOtherField)`.
- **Reading field state in templates**: `myForm.fieldName()` returns a
  `FieldState` with `.value()`, `.touched()`, `.invalid()`, `.errors()`
  etc., all signals.
- **Submission**: `submit(form, async () => { ... return undefined; })`.
  Returning `undefined` means success; the return type is
  `TreeValidationResult` which accepts `null | undefined | void` for
  success. This project never wires server-side validation errors back
  into field-level state — failures are surfaced via a snackbar/banner
  instead, which was a deliberate scope/complexity tradeoff, not a
  limitation of the API.

---

## Milestone summary

1. **Foundation** — Material setup, design tokens, models for every API
   entity, `AuthService`/`TokenStorageService`/`AppConfigService` (the
   last of these later removed in Stage 5 — see "Team vs Project label"
   above), the auth interceptor (401 → refresh → retry, with
   request-queuing so concurrent 401s trigger exactly one refresh call),
   route guards, the login page (first real Signal Forms usage), app
   shell.
2. **Teams** — full CRUD, membership management (add via searchable
   user picker, remove, primary toggle), Team/Project label applied
   throughout.
3. **Bitzas core** — the tree browser (`/bitzas`, `/bitzas/:id`),
   breadcrumb powered by `GET /bitzas/{id}/ancestors` (one call;
   originally built client-side via RxJS `expand` walking `parent_id` one
   hop at a time — replaced once the endpoint was added during Stage 4),
   create/edit with kind-conditional fields, retire/reactivate,
   reassign-project with cascade_scope, category management, QR label
   generation + a `/bitza/:id` → `/bitzas/:id` redirect route matching
   the exact singular path the docs say gets baked into printed physical
   tags.
4. **Bitza actions** — checkout/check-in (status always derived from
   history, never a stored field, matching the backend design exactly),
   stock adjustments (in/out toggle → signed delta, live negative-result
   preview, 422 handling), image gallery (upload/set-cover/delete,
   authenticated blob fetching as described above).
5. **Admin & polish** — users admin (create/edit/suspend/delete, with the
   permission table's actual nuance enforced: role-change is
   superuser-only, suspend/delete works for superuser-on-anyone or
   admin-on-plain-users, nobody can act on their own account), audit log
   with user/action filters, plus a dedicated accessibility pass (see
   below).
6. **Post-reconciliation and fixes (Stages 4–5)** — `/me` personal
   landing page and its default-login-route wiring; `kind` editability
   (conditional on checkout/stock-log history, confirmation dialog,
   "Type" as the UI label) plus its own missed guard (stock bitzas
   can't have children — enforced on create, move, and the kind
   transition itself, with matching frontend disable/hide treatment);
   root bitza locked to name-only/admin-only editing, both backend and
   frontend; Team→Project label rip-out (`AppConfigService` removed).
   See `bitza_project_context.md` for the current backend shape of all
   of this, and `bitza_open_issues.md` for what's next.

---

## Schema drift between frontend models and the live backend — resolved

**This is done and no longer tracked in a dedicated document** — the
16-patch history has been dropped in favor of the durable lesson: the
frontend was originally built from `bitza_project_context.md`'s prose
description of the API, and in several places that description (and
therefore the frontend) had drifted from what the backend's actual
Pydantic schemas define. Five things were confirmed completely
non-functional purely from field-name/polarity mismatches — creating a
user (missing required `display_name`), suspend/unsuspend (backend
`is_active`, opposite polarity from the frontend's old `is_suspended`),
checkout holder display (`holder_id` vs `user_id`), team member names
(`user_display_name` vs assumed `username`/`email`), and audit log
summaries (`description` vs `summary`) — found by reading
`backend/app/schemas/*.py` directly, not by reproducing a failure. A
follow-up completeness pass surfaced two more live bugs from a different
root cause: list endpoints deliberately return a more compact schema than
detail endpoints, and the frontend had been using one TypeScript type for
both, silently dropping fields the list response never actually sent
(exact-mode stock quantities and team descriptions both went blank in
grid/table views for exactly this reason). **Auth** (`schemas/auth.py`)
was the one area confirmed to have no drift at all.

**The `GET /api/v1/users/` permission question is resolved too** — it's
genuinely, deliberately admin/superuser-gated, which broke the
team-member-add picker for any non-admin user. Fixed by adding a new
`GET /users/directory` endpoint (any authenticated user, id +
display_name only) rather than relaxing the existing gate.

**Two design questions came out of this work — both resolved and built**
during Stage 4: a personal `/me` landing page (`GET /checkouts/mine`,
`GET /projects/mine` — see `bitza_project_context.md`), and `kind`
editability, relabelled "Type" in the UI (see `bitza_project_context.md`'s
`kind` section for the final conditional-editability rules).

---

## Known bugs found and fixed this session

Worth knowing about even though they're resolved, since a couple point at
a process risk rather than a one-off mistake:

- **Milestone 4 was silently unwired.** `CheckoutSection`, `StockSection`,
  and `ImageGallery` were built correctly but never actually imported or
  rendered by `bitza-browser.ts` — nothing in the app could reach them.
  Git showed `bitza-browser.ts` hadn't been touched since the Milestone 3
  commit. Root cause: milestones were incorporated into the real repo by
  overlaying new/changed files from each zip onto the existing tree
  rather than a clean replace, which silently drops changes to
  already-existing files. **Fixed** — `bitza-browser.ts` now correctly
  wires all three in. If future milestones get incorporated the same
  overlay-style way, watch for this same failure mode again.
- **Stale default scaffold files.** `app.html`/`app.scss` — the original
  `ng new` welcome-page files, deleted in Milestone 1 when `App`'s
  template moved inline — were still sitting in the repo, unreferenced,
  for the same overlay-merge reason above (a zip that *removes* a file
  can't make an overlay-based incorporation remove it too). Deleted.
- **Shell brace-expansion bug (already resolved, no lingering effect).**
  Early on, `mkdir -p path/{a,b,c}` was used to set up feature folders;
  the sandbox's shell doesn't support brace expansion, so this created
  one literally-named `{a,b,c}` directory instead of three, which showed
  up as harmless clutter in a couple of delivered zips. No source files
  were ever actually misplaced (file creation always auto-creates correct
  parent directories regardless of what `mkdir` did) — this was cleaned
  up and confirmed empty before removal.

---

## Testing state

- **The project owner is now running the frontend against a live backend
  directly** and using that to decide what needs fixing — this is new as
  of Stage 5, and is how Stage 5's four issues were found. It's real
  verification but not exhaustive: no formal QA pass, no systematic
  click-through of every screen, ongoing rather than complete. Treat
  "hasn't been reported as broken" as weaker evidence than "confirmed
  working," and expect further issues to keep surfacing this way rather
  than through code review alone.
- **42 unit tests across 11 spec files**, all at the service layer
  (`core/services/*.spec.ts`) plus one guard spec
  (`core/guards/redirect-to-root.guard.spec.ts`), using
  `HttpTestingController` to assert on request method/URL/body/params —
  not component tests. Unchanged since the `/me`/`kind`-editability work;
  Stage 5's four fixes added no new tests (matches the "no
  component-level tests exist" gap below — the components touched had
  none to extend).
- **No component-level tests exist.** Nothing exercises a component's
  template, user interactions, or rendered output.
- **No e2e tests.**
- **No automated accessibility tooling has been run** (no axe-core, no
  Lighthouse pass). The accessibility fixes made during Milestone 5 were
  found by manually reading Material's compiled source to check specific
  claims (e.g. confirming `mat-card-title` has no forced host element and
  produces no heading semantics on its own; confirming `mat-icon` sets
  `aria-hidden="true"` on itself by default) and then patching the
  specific gaps that fell out of that — not from a systematic scan. Fixed
  so far: a skip-to-content link, real `<h1>`/`<h2>` headings on pages
  that only had styled-but-non-semantic `mat-card-title` text, a
  keyboard/ARIA fix for clickable Material cards (missing `role="button"`
  and Space-key support), one icon-only button with no accessible name at
  all (relied solely on a hover tooltip), and meaningful alt text on
  gallery images (was `alt=""`, wrong for non-decorative content). A full
  systematic pass (real axe run, keyboard-only walkthrough, screen reader
  spot-check) has not happened.

---

## Deliberately out of scope / deferred

Carried over from the backend docs' own "deliberately deferred" list,
plus a few frontend-specific scope cuts made along the way:

- **In-app barcode/serial scanner** (camera-based, for manufacturer
  codes) — the backend docs defer this explicitly; the frontend's QR
  route/label support (the *primary* scan mechanism) is built.
- **Comp/trip packing lists** — no backend support exists; not built.
- **Image thumbnails in list/table views** — scope cut to avoid an
  authenticated-blob-fetch-per-row cost; detail-view-only for now.
- **Cross-bitza checkout/stock dashboards** ("what's currently checked
  out" across the whole club, "recent stock activity" feed) — nothing in
  the docs originally asked for this; only per-bitza history exists.
  **Partially built** — a personal (not club-wide) version of "what's
  checked out" now exists as the `/me` landing page (`GET
  /checkouts/mine`, `GET /projects/mine` — see `bitza_project_context.md`).
  Still not built: low-stock alerts, and a "recent activity" feed — the
  latter was explicitly left undecided, not just unbuilt.
- **Component test suite, e2e suite, real accessibility audit** — see
  Testing state above.
- **Milestone 1–4 inline-template retrofit** — see Architecture
  conventions above.

---

## Environment notes

- **Node**: `frontend/.nvmrc` pins `v24.16.0`, which comfortably clears
  Angular 22 CLI's floor. A sandboxed dev environment used during this
  build was stuck on an older patch version and needed a local,
  never-shipped patch to the CLI's own version-gate check purely to run
  `ng build`/`ng test` for verification — this has no bearing on the real
  project and isn't part of any delivered code.
- **Package manager**: npm, lockfile (`package-lock.json`) is committed
  and should stay that way — this is an application, not a published
  library, so reproducible installs matter. A `.gitignore` mistake early
  on caused it to be excluded for a while; that's been corrected in all
  three of the project's `.gitignore` files (root/backend/frontend).
