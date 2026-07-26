# Bitza — project context

Project-specific decisions and contracts for the Bitza asset management app.
Use this document alongside the general FastAPI and Angular context instructions.
It covers things that are specific to this project rather than general tooling patterns.

---

## What Bitza is

Originally built for tracking the location and quantity of physical assets —
electronic components, tools, and miscellaneous items — around a home
workshop. The name comes from "bitza this and bitza that".

It has since been redesigned to also serve a second, richer deployment: a
community or student club working on either individual or group projects where
they may be divided into teams working on different aspects of a project. Members
can join more than one team. It is expected that members may drop in an out of the
project over time, with members changing teams or projects as needed. There can be
club-wide and team-specific equipment. Rather than fork the codebase, **one
unified data model serves both** — the home case is simply the degenerate
case of the club model (one team, often one member).

Stack:
- **Backend** — FastAPI + SQLite, `bitza/backend/`
- **Frontend** — Angular, `bitza/frontend/`

### Design philosophy

Two decisions run through everything below and explain most of the choices
that might otherwise look inconsistent:

1. **Design around the questions people actually ask, not a physically
   accurate model of reality.** Early design passes tried to model teams,
   locations, and items as faithfully as possible and produced a schema
   that was accurate and unusable. Everything since has been driven by
   "what do I actually want to know" — e.g. "where does this live when
   nobody has it" and "who do I ask about this", not "where precisely is
   this object at this instant".

2. **Record reality, don't enforce policy.** There is no ownership, no
   access control, and no approval workflow anywhere in the item/team
   model. Any authenticated user may create, edit, move, retire, check
   out, or adjust stock on anything, and may add or remove any user from
   any team. This is a deliberate trust decision, not an oversight — see
   "Permissions" below. Phase 1 (accounts, roles, suspension) is the one
   place real access control exists, and it is untouched by any of this.

---

## Auth contract (backend → frontend)

**Unchanged from the original design — Phase 1 was never touched by the
Team/Bitza redesign.**

The backend uses a dual-token JWT system. The frontend is responsible for
managing both tokens client-side.

### Login

```
POST /api/v1/auth/login
{"identifier": "email or username", "password": "..."}

→ {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

`identifier` accepts either an email address or a username — not two separate
fields. The login form should have a single identifier input.

### Authenticated requests

Send the access token as a Bearer header on every API call:

```
Authorization: Bearer <access_token>
```

### Token storage

Both tokens are returned in the response body (not as cookies). Store them
in `localStorage`. If XSS risk becomes a concern in future, the backend would
need to be updated to set httpOnly cookies instead — that is a backend change,
not just a frontend one.

### Token expiry and refresh

- Access token: **15 minutes**
- Refresh token: **30 days**

The Angular app must intercept 401 responses, attempt a token refresh, and
retry the original request. If the refresh also fails (token revoked or
expired), redirect to the login page and clear stored tokens.

```
POST /api/v1/auth/refresh
{"refresh_token": "..."}

→ {"access_token": "...", "refresh_token": "..."}
```

Refresh is **rotational** — the old refresh token is invalidated on every
successful refresh call. Always store the new refresh token from the response,
never reuse the old one.

### Logout

```
POST /api/v1/auth/logout
{"refresh_token": "..."}

→ 204 No content
```

On logout: call the endpoint, then clear both tokens from localStorage
regardless of the response (the access token is short-lived anyway).

---

## Password strength (frontend + backend)

Unchanged. The backend enforces:
- Minimum 12 characters, maximum 128
- zxcvbn score ≥ 3

The frontend should provide **advisory** real-time feedback using the
`zxcvbn` npm package (not a blocking gate — the backend is authoritative).
Show a strength indicator as the user types. Do not block form submission
on the frontend strength check alone; let the backend return a 422 if the
password fails.

---

## User roles (Phase 1 — unchanged)

Three roles: `superuser`, `admin`, `user`. The current user's role is
available in the `GET /api/v1/users/me` response. This governs account
management only — it has **no bearing** on anything in the Team/Bitza model
below except one thing: hard-deleting a Bitza is admin/superuser only.

| What to show/hide | superuser | admin | user |
|---|---|---|---|
| User management section | ✓ | ✓ | ✗ |
| Create admin option in user form | ✓ | ✗ | ✗ |
| Role change controls | ✓ | ✗ | ✗ |
| Suspend / delete user controls | ✓ | users only | ✗ |
| Audit log | ✓ | ✓ | ✗ |
| Hard-delete a bitza | ✓ | ✓ | ✗ |
| Everything else in this document | ✓ | ✓ | ✓ |

The backend enforces all permissions — the frontend role checks are purely
for showing and hiding UI elements. Never rely on frontend role checks for
security.

---

## Permissions in the Team/Bitza model — the trust model

This is the one section worth reading before anything else, because it's
easy to assume more restriction exists than actually does.

**Any authenticated user may, with no approval and no ownership check:**
- Create, rename, or delete a team (delete is blocked only if a bitza still
  references it)
- Add any user to any team, or remove any user from any team — including
  removing someone else, not just themselves
- Create, edit, move, retire, or reactivate any bitza, regardless of who
  created it or which team is responsible for it
- Check out or check in any mobile bitza
- Adjust stock quantity or fuzzy state on any stock bitza

**The only two exceptions anywhere in this model:**
- **Hard delete of a bitza** — admin/superuser only. See "Retiring vs
  deleting" below for why this is the one place a floor exists.
- **Viewing the audit log** — admin/superuser only (unchanged from the
  original Phase 2 design).

Why so open: club membership is transient (people stop turning up, lose
interest, or simply forget which team they're nominally on), and the
alternative — some kind of ownership or approval gate — was tried in early
design passes and consistently added friction without adding real value,
since the actual failure mode this app cares about is bad *data entry*
("Fred says team X has the last torque wrench, but it's actually with Dave"),
not bad *authorisation*. If someone abuses this trust, that's a
conversation with that person, not a feature request.

---

## Teams

`Team` is the universal "who's responsible for this" entity. It serves two
purposes that look different but are structurally identical:

- **Club deployment**: a dozen-plus real teams (Aero, Suspension, Battery, a
  "Workshop" team standing in for what would otherwise be a special
  "workshop manager" role — see below), each with several members.
- **Home deployment**: one team, or a handful for distinct projects.

**"Team" vs "Project" is a display-label choice, not a schema difference.**
The database and API are named `Team` throughout — the Angular frontend
carries a simple config that swaps the label to "Project" for home-style
deployments. Nothing else changes.

### Workshop manager is not a special role

There is no `is_workshop_manager` flag anywhere. "Workshop manager" (and
"assistant workshop manager") is just membership of a `Team` named
"Workshop" — indistinguishable in the schema from being on any other team.
Most workshop managers are also on a regular team at the same time, which
is why membership is many-to-many, not a single field on `User`.

### Membership

`TeamMember` is a plain many-to-many join (`user_id`, `team_id`) — **no
history, no start/end dates, no "team lead" flag.** A user can belong to
zero, one, or many teams simultaneously. Leaving a team is a row deletion,
full stop; "who was on what team when" was explicitly ruled out as a
requirement.

`is_primary` on a membership row marks at most one team as a given user's
default (enforced by unsetting any existing primary in the same transaction
when a new one is set — the same rotation pattern used for refresh tokens).
It carries **no permission meaning whatsoever** — its only purpose is
pre-filling the `team_context` field when checking out a mobile bitza. It's
fully overridable at checkout time (e.g. helping out a team you're not on).

```
GET    /api/v1/teams/                      List all teams
GET    /api/v1/teams/?user_id=<id>         Teams a specific user belongs to
POST   /api/v1/teams/                      Create a team
GET    /api/v1/teams/{id}                  Get a team
PATCH  /api/v1/teams/{id}                  Rename / describe
DELETE /api/v1/teams/{id}                  Delete (409 if any bitza still responsible-to it)

GET    /api/v1/teams/{id}/members          List members
POST   /api/v1/teams/{id}/members          Add a member  {user_id, is_primary?}
PATCH  /api/v1/teams/{id}/members/{user_id}  Set/unset primary  {is_primary}
DELETE /api/v1/teams/{id}/members/{user_id}  Remove a member
```

---

## Bitzas — the unified location/container/item model

**This is the core redesign.** The original model had three separate
tables — `StorageLocation`, `LocationDetail`, `Asset` — and the design
process eventually concluded there's no real difference between a shelf, a
toolbox, and a multimeter except one axis: can it be checked out. Rather
than model "reality" (a shelf is structurally a container, a tool is
structurally an item), the schema now asks the one question that actually
matters and collapses everything into a single self-referential tree.

Everything the club or a home user owns — rooms, shelves, toolboxes, tools,
consumables — is a **`Bitza`**. What distinguishes them is the `kind` field:

| `kind` | Examples | Checkoutable? | Has quantity? |
|---|---|---|---|
| `fixed` | room, shelf, pegboard | No | No |
| `mobile` | multimeter, toolbox, torque wrench | Yes | No |
| `stock` | resistors, screws, zip ties | No | Yes (see below) |

A toolbox is `fixed` in the sense that it's a container holding other
bitzas — but note a toolbox could equally be modelled as `mobile` if you
want to check the *whole box* out as a unit; the model doesn't force a
choice here, it's just data.

### Hierarchy

`parent_id` is a nullable self-referential FK. `NULL` = a root (e.g.
"Workshop", "Garage"). Depth is unlimited — a bitza's "home" is simply
wherever its `parent_id` currently points.

**Moving a container never touches its contents.** If Toolbox 3 moves from
the study to James' room, every tool inside it is still correctly located
with zero changes — they point at the toolbox, not the room. This was
verified explicitly during design and is the main reason the tree model
works as well as it does for a workshop that gets reorganised often.

**Reads never traverse the full subtree.** Per the general FastAPI/SQLite
instructions, `GET /bitzas/?parent_id=X` returns direct children only — a
single non-recursive query. If the frontend wants "everything on Shelf 4
including inside its boxes", it drives that by issuing repeated
direct-children requests itself. The one exception, and it's a *write*-path
exception, is described under "Reassigning responsible team" below.

There is **no privacy feature**. An earlier design pass added
private/shared visibility flags on locations; it was removed entirely as a
misfeature — the one real use case ("this is Fred's personal multimeter, not
the club's") is adequately handled by writing "belongs to Fred" in the
description field, and everything else privacy would have added (cascade
rules, opaque 404s, permission checks on every read) wasn't worth it for a
club or household where everyone already knows each other.

### Responsible team — a snapshot, not a live inherited link

`responsible_team_id` is **required at creation** and purely informational
— "who to ask about this", never a permission gate (see "Permissions"
above). Critically, it does **not** automatically follow a parent's team if
the parent's responsibility changes later — it's a snapshot, set once at
creation, and only ever changes via an explicit edit or the reassign-team
sweep below.

The frontend is expected to pre-fill `responsible_team_id` from the parent
bitza's value when adding a child under an existing one (since it already
has the parent loaded to navigate there) — the backend only validates that
a team was supplied and that it exists; it never infers or resolves a value
itself.

### Retiring vs deleting

Any authenticated user may flag a bitza as **retired** — lost, broken,
can't be reordered (`discontinued`), or replaced by a substitute
(`superseded`) — via `POST /bitzas/{id}/retire`. This is a status flag, not
a workflow: no approval, no confirmation step, fully reversible via
`POST /bitzas/{id}/reactivate` (e.g. the "lost" multimeter turns up again).

**Hard delete (`DELETE /bitzas/{id}`) is admin/superuser only**, and reserved
for records that genuinely should never have existed — duplicates, test
entries. Never use it for "this got lost" — that's what retire is for. This
is the one place a permission floor exists in the whole item model, because
delete makes the record disappear entirely, whereas retire keeps it
(and its history) around and reversible.

```
POST /api/v1/bitzas/{id}/retire      {reason, note?}   any user
POST /api/v1/bitzas/{id}/reactivate                     any user
DELETE /api/v1/bitzas/{id}                              admin/superuser only, 409 if it has children
```

`GET /api/v1/bitzas/?status=retired&retired_reason=broken` doubles as the
"admin report" use case — it's just a filtered list, not a special endpoint,
and it's open to any user like every other read in this model.

### Reassigning responsible team — the one deliberate cascade

An ordinary `PATCH /bitzas/{id}` may change `responsible_team_id`, but it
**only ever touches that one row** — no matter what `kind` the bitza is.
Cascading to children is never an implicit side-effect of an edit.

When a genuine sweep is wanted (e.g. "the battery team is taking the two
bottom shelves of the brown cupboard"), use the dedicated endpoint:

```
POST /api/v1/bitzas/{id}/reassign-team
{"team_id": "...", "cascade_scope": "none" | "direct_children" | "all_descendants"}
```

`cascade_scope` is **required** — the backend never guesses a default. Which
scope actually makes sense depends on the bitza's mobility, but that's a
**frontend UX default, not a backend rule**: a cupboard's reassign dialog
might default its scope picker to `none` (moving the cupboard between teams
doesn't necessarily move what's sitting on its shelves), while a toolbox's
might default to `all_descendants` (the tools inside travel with it). Either
can always be overridden by the person doing it.

`all_descendants` is the **one deliberate exception** to "never traverse the
full subtree on the backend" — it's a rare, explicit write operation, walked
level-by-level via repeated direct-children queries in the service layer
(not a single recursive SQL statement), and produces exactly one audit log
entry summarising the whole sweep (count + old/new team), not one entry per
affected row.

### Checkout (kind = `mobile`)

"Currently checked out" is always **derived** — a `Checkout` row with
`checked_in_at IS NULL` — never a separately maintained state field. There
are no due dates and no approvals; this is deliberately just state, not a
workflow.

```
POST /api/v1/bitzas/{id}/checkout   {team_context?, note?}   → 201, the open Checkout
POST /api/v1/bitzas/{id}/checkin    {note?}                  → 200, the closed Checkout
GET  /api/v1/bitzas/{id}/checkouts                           → history, newest first
```

The holder is always the current authenticated user — there is no checking
something out on someone else's behalf. Anyone may check something *in*,
not just whoever checked it out (e.g. "I found this lying around and
returned it").

`team_context` is a **free-text snapshot**, not a live FK to `Team`. If
omitted, it's pre-filled from the holder's primary `TeamMember` at the
moment of checkout, but it's just a string from then on — if that team
membership is later removed entirely, the historical checkout record is
completely unaffected. This snapshot behaviour is what makes it safe for a
person checking out a tool to log it against a team they're just helping
that day, without corrupting anything.

### Stock (kind = `stock`)

Two sub-modes, chosen per bitza via `stock_mode`:

- **`exact`** — `quantity` is a real integer, changed only via
  `POST /api/v1/bitzas/{id}/stock-adjustments {delta, note?}` (positive =
  stock in, negative = stock out; rejected with 422 if the result would go
  negative). This produces a `StockLog` row every time — a lightweight
  who/when/how-much record. This is deliberately **not** forensic-audit
  tooling (no reconciliation, no valuation, no stock-take workflow) — it
  exists purely to answer "who used the last one" and "how often does this
  get used", nothing more.
- **`fuzzy`** — `fuzzy_state` (`plentiful` / `low` / `empty`) is edited
  directly via a normal `PATCH /bitzas/{id}` — **no log at all**, since
  fuzzy stock is explicitly approximate and not worth tracking precisely.

`quantity` is never editable via plain `PATCH` — only through the
adjustments endpoint, so the log always stays complete for exact-mode stock.

```
POST /api/v1/bitzas/{id}/stock-adjustments   {delta, note?}   → 201
GET  /api/v1/bitzas/{id}/stock-adjustments                    → history, newest first
```

### Images

A bitza may have multiple images, exactly one of which is `is_primary`
(the cover photo for list views). The first image ever uploaded for a
bitza is automatically made primary regardless of what's requested — there
should never be a bitza with images but no designated cover photo.

```
GET    /api/v1/bitzas/{id}/images                metadata list
POST   /api/v1/bitzas/{id}/images                multipart upload, {file, is_primary?}
GET    /api/v1/bitzas/{id}/images/{image_id}     the actual file (authenticated — see below)
PATCH  /api/v1/bitzas/{id}/images/{image_id}     {is_primary: true} to change the cover photo
DELETE /api/v1/bitzas/{id}/images/{image_id}     if it was primary, the oldest remaining image is promoted
```

Angular clients must fetch image files via `HttpClient` with
`{ responseType: 'blob' }` and build an object URL — plain `<img src>` will
not send the Authorization header, and there's no unauthenticated static
path for these files.

### Acquisition / provenance

`purchased_by_user_id` doubles as "added by" — the project deliberately
decided these never need separating ("all I really need to record is that
it was purchased by B for team X", regardless of who physically typed the
entry into Bitza). Defaults to the creating user if not supplied explicitly.
`vendor`, `purchase_date`, `order_url` are free-form, all optional.

### Categories

Unchanged in behaviour from the original design — free-standing, unique
names, deletion blocked while any bitza still references it.

```
GET/POST   /api/v1/categories/
PATCH/DELETE /api/v1/categories/{id}
```

### Listing and filtering

```
GET /api/v1/bitzas/
    ?parent_id=<id>            direct children of this bitza
    ?root_only=true            top-level bitzas only (ignored if parent_id set)
    ?kind=fixed|mobile|stock
    ?status=active|retired
    ?responsible_team_id=<id>
    ?category_id=<id>
```

No privacy filtering exists — every bitza is visible to every authenticated
user regardless of who created it or which team is responsible for it.

---

## API base URL and versioning

Unchanged. All endpoints are prefixed with `/api/v1/`.

```
# environments/environment.ts
apiUrl: 'http://localhost:8000/api/v1'

# environments/environment.prod.ts
apiUrl: 'https://<your-domain>/api/v1'
```

The health check endpoint (`/health`) is at the root, not under `/api/v1/`.

---

## Scanning — QR/NFC, deliberately backend-light

Physical tags on bitzas encode a plain frontend URL —
`bitza.myclub.org.au/bitza/<id>/` — not an opaque code the backend has to
resolve. This needs **zero backend support**: the ID is already in the URL
a scanner navigates to, the frontend calls the ordinary
`GET /api/v1/bitzas/{id}` from there, and printing a new label is a pure
client-side function (build the URL from an ID you already have, render a
QR image) with nothing to persist.

This intentionally does not cover manufacturer/supplier barcodes whose
content Bitza can't control (a resistor reel's EAN-13, a multimeter's
serial sticker) — resolving those would require an in-app camera-based
scanner and a backend lookup table, which is real, currently-unproven scope.
**Deferred to the future roadmap** — see below.

---

## Future roadmap (deliberately not built yet)

Both of these were designed around explicitly, so that adding them later
should be additive rather than a refactor:

- **In-app scanner for pre-existing manufacturer/supplier codes.** Would
  need a small `external_code` lookup (single column or child table, TBD)
  plus a camera-based decode-and-register flow in the Angular app. Skipped
  for now — may never be worth building if adoption never reaches the point
  where it matters.
- **Comp/trip packing lists** (e.g. "what needs to go to Melbourne this
  year"). Structurally a many-to-many between bitzas and a new
  `PackingList`/`PackingListItem` pair, with a per-pairing status
  (`needs_packing` / `packed` / `returned`). Deliberately kept independent
  of `responsible_team_id`, `parent_id`, and checkout state — ticking
  "needs to be packed" is a planning decision, physically moving something
  to "comp trailer" is a separate `parent_id` update, and neither should
  affect who's responsible for the item. Keeping those three axes
  independent now is what keeps this a pure addition later.

---

## Known decisions still to be made (frontend)

- **Token refresh strategy** — interceptor-based (transparent to the rest of
  the app) vs explicit refresh calls. Interceptor is strongly recommended.
- **Session persistence** — does the app stay logged in across browser
  restarts? (Yes if using localStorage, no if sessionStorage.)
- **Team vs Project label config** — where this toggle lives in the Angular
  build (environment file vs runtime setting) hasn't been decided.
- **Cascade-scope default heuristics** — whether the frontend infers a
  sensible default scope from a bitza's `kind` (see "Reassigning
  responsible team" above) or always asks explicitly.
- **Offline behaviour** — out of scope for now; SQLite backend has no sync
  capability.
