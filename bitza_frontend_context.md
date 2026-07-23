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
  services/     one per resource (TeamService, BitzaService, UserService, ...),
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
- **Team vs Project label**: `AppConfigService` holds this as a runtime
  signal, persisted to `localStorage`, not a build-time environment
  value — deliberately, so a single deployment could flip the label
  later from a settings screen (none exists yet) without a rebuild.
- **`cascade_scope` UI defaults** (reassign-team dialog): `fixed`/`stock`
  → `none`, `mobile` → `all_descendants`, always overridable. This is
  frontend-only convenience — the backend never infers or defaults this
  and always requires it explicitly, per the backend docs.
- **Authenticated image fetching**: there's no unauthenticated static
  path for bitza images, so `ImageGallery` fetches every file via
  `HttpClient` with `responseType: 'blob'` and builds object URLs,
  revoking them both on list changes and component destroy. Deliberately
  does **not** show thumbnails in any list/table view (would mean an
  authenticated blob fetch per row) — images are detail-view-only for now.

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
   entity, `AuthService`/`TokenStorageService`/`AppConfigService`, the
   auth interceptor (401 → refresh → retry, with request-queuing so
   concurrent 401s trigger exactly one refresh call), route guards, the
   login page (first real Signal Forms usage), app shell.
2. **Teams** — full CRUD, membership management (add via searchable
   user picker, remove, primary toggle), Team/Project label applied
   throughout.
3. **Bitzas core** — the tree browser (`/bitzas`, `/bitzas/:id`),
   breadcrumb built client-side by walking `parent_id` via RxJS `expand`
   (the backend never recurses — direct-children-only reads, by design),
   create/edit with kind-conditional fields, retire/reactivate,
   reassign-team with cascade_scope, category management, QR label
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

---

## Assumptions needing backend confirmation

None of these are hypothetical risk-aversion — each one is flagged inline
in the relevant service file's doc comment too, but consolidating them
here since they cut across milestones:

1. **`GET /api/v1/users/`** — the docs say the `/users/` directory is
   admin/superuser-gated, but the Team/Bitza trust model requires any
   user to be able to add any other user to any team, which needs some
   way to browse/look up users. The frontend calls `GET /users/` as the
   natural read for both the team-member-add picker (Milestone 2) *and*
   the admin users list (Milestone 5) — for the latter it's genuinely
   meant to be gated, so this probably needs to resolve as "list reads
   are open, only mutations are gated," but that's a guess. **Check this
   against the actual backend before relying on either UI flow.**
2. **Admin user CRUD shapes** (`POST /users/`, `PATCH /users/{id}`,
   `DELETE /users/{id}`) — the docs describe the *permission table* for
   account management but never the request/response shapes. The
   frontend assumes plain REST shapes matching the rest of the app's
   style, and models suspend/unsuspend as a plain `PATCH
   {is_suspended: bool}` rather than a dedicated endpoint (there's no
   documented precedent either way). See `user.model.ts`'s
   `UserCreate`/`AdminUserUpdate` doc comments.
3. **Audit log filter params** — assumed `GET /audit/?user_id=&action=`
   works as a query-string filter; never confirmed against a real
   endpoint.

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

- **35 unit tests across 10 spec files**, all at the service layer
  (`core/services/*.spec.ts`), using `HttpTestingController` to assert on
  request method/URL/body/params — not component tests.
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
  the docs asked for this; only per-bitza history exists.
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
