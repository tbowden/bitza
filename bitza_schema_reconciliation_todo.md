# Bitza — frontend/backend schema reconciliation

**Status: the schema-reconciliation work below is done.** 16 patches
(`0001`–`0016`), applied and pushed. Everything in "Confirmed
likely-broken" and "Confirmed missing but harmless" is resolved. What's
left, and what's new: the inert `stock_mode` dropdown (still open), the
`get_ancestors` endpoint (still just a suggestion), and two new design
questions raised after review — a personal `/me` landing page, and
`kind` editability/labelling — both below in their own section, neither
implemented yet. **If you're picking this up fresh, skip straight to
"New design questions raised" and "Suggested approach for the new
chat" at the bottom; the rest of this doc is now a historical record of
what was found and fixed, kept for context.**

For full project orientation, see `bitza_context_restoration.md`; for
frontend architecture generally, see `bitza_frontend_context.md`. This
document was originally scoped to one problem: the Angular frontend was
built from `bitza_project_context.md`'s prose description of the API,
not from the live backend schemas — and in several places, reality and
the docs (and therefore the frontend) had drifted apart. That was
confirmed by reading the actual `backend/app/schemas/*.py` files
directly against the frontend's `frontend/bitza/src/app/core/models/*.ts`
files, not by observing a failure — this project still has never had a
live click-through against a running backend+frontend together (see
`bitza_frontend_context.md`'s "Stage 3 caveats").

Auth (`schemas/auth.py`) was checked and has **no** drift — Phase 1's
contract is accurate and unchanged. Everything below is Team/Bitza-model
territory (Stage 2 onward).

---

## Confirmed likely-broken — fix these first

**✅ All five resolved.** Patches `0001`–`0006`, `0009`. Kept below as
the original diagnosis for reference.

These aren't missing nice-to-haves. Each one is a field-name or polarity
mismatch between what the backend actually sends/expects and what the
frontend reads/sends. None of this had a live click-through against a
real backend at the time these were written (see
`bitza_frontend_context.md`'s "Stage 3 caveats"), so these were confirmed
by reading source on both sides, not by reproducing the failure.

### 1. Create User is likely completely broken
- Backend `UserCreate` (`schemas/user.py`) **requires** `display_name`
  (`str, min_length=1, max_length=150`).
- Frontend `UserCreate` (`user.model.ts`) has no `display_name` field at
  all, and `UserFormDialog` never collects or sends one.
- Expected result today: every create-user submission gets rejected with
  a 422 the UI doesn't specifically explain.

### 2. Suspend/Unsuspend is likely completely broken
- Backend uses `is_active: bool` on `UserRead`/`UserUpdate` — **opposite
  polarity** from what the frontend assumes.
- Frontend uses `is_suspended: bool` throughout (`User` model,
  `AdminUserUpdate`, `UsersList`'s status column and toggle logic).
- This is worse than a rename: the frontend's status badge will show
  every user as "active" regardless of real status (since
  `user.is_suspended` is always `undefined`/falsy), and the toggle sends
  `{is_suspended: !user.is_suspended}` — a field name the backend
  doesn't have — so it silently does nothing.
- Fix needs to flip the boolean logic throughout, not just rename the
  field (`is_active: true` ↔ `is_suspended: false`).

### 3. Checkout holder is likely never resolved or displayed correctly
- Backend `CheckoutRead` (`schemas/bitza.py`) uses `holder_id` (and
  provides `holder_display_name` directly — see the audit-log note below
  for why that matters).
- Frontend `Checkout` model (`checkout.model.ts`) uses `user_id`, and
  `CheckoutSection` reads `checkout.user_id` in three places.
- Expected result: `checkout.user_id` is always `undefined`, so the
  "checked out by" line renders blank, and the batched-lookup code
  (`forkJoin` over unique user ids) ends up looking up `undefined`,
  producing a wasted invalid request per render.
- **Bonus finding while fixing this**: the backend already returns
  `holder_display_name` directly on `CheckoutRead` — the frontend's
  entire "batch-fetch usernames via `UserService.get()`" mechanism in
  `CheckoutSection` may not even be necessary anymore. Worth checking
  whether the backend enrichment is sufficient before keeping that logic.

### 4. Team members table probably shows raw UUIDs instead of names
- Backend `TeamMemberRead` (`schemas/team.py`) provides
  `user_display_name` directly.
- Frontend `TeamMember` model guessed `username`/`email` as possibly-embedded
  fields (its own doc comment even flagged this as unconfirmed:
  *"Convenience fields the list endpoint is expected to embed... confirm
  against the actual backend response"*) — turns out neither exists;
  `user_display_name` is the real field.
- `TeamDetail`'s members table does `{{ member.username ?? member.user_id }}`
  — always falls through to the raw id.
- Note: membership mutation routes (`PATCH`/`DELETE
  /teams/{team_id}/members/{user_id}`) **were** verified against
  `endpoints/teams.py` and **do** match what `TeamService` already sends
  — only the display field is wrong, not the routing.

### 5. Audit log summaries are likely always blank
- Backend `AuditLogRead` (`schemas/audit.py`) uses `description`.
- Frontend `AuditLogEntry` model uses `summary`.
- `AuditLog`'s template renders `{{ entry.summary }}` — always blank
  against the real backend.
- **Bonus finding**: `AuditLogRead` also already provides
  `user_display_name` directly, and additionally provides `entity_type`/
  `entity_id` (what kind of record, which specific one) that the frontend
  currently drops entirely. The `AuditLog` component's batched
  `UserService.get()` lookup logic (mirroring the same pattern built for
  checkouts) is very likely unnecessary for the same reason as #3 —
  the backend already did this work. `entity_type`/`entity_id` are a real
  product gap worth adding to the table (e.g. "bitza: Multimeter" instead
  of just a bare action string), not just a naming fix.

---

## Confirmed missing but harmless — completeness pass, lower urgency

**✅ Resolved, except the `stock_mode` dropdown item (still open — see
below).** Patches `0010`–`0016`. Two real, live bugs were found *while*
doing this pass, both from properly splitting list-response types from
detail-response types (the frontend had been using one type for both,
which papered over the fact the backend deliberately sends less data to
list views): exact-mode stock quantities were showing blank in the bitza
children table (`stock_mode` was never actually in the list response),
and team descriptions have never rendered in the teams grid (same
issue — `description` was never in the list response either). Both
fixed alongside the type corrections.

These were real gaps (backend sends more than the frontend models
captured, or a frontend field was outright invented and didn't exist
backend-side), but nothing was reading the missing/wrong fields, so
there was no live breakage from the gaps themselves — the two live bugs
above came from the list/detail typing issue the gaps led to, not from
the missing fields directly.

- **Bitza** (`schemas/bitza.py` `BitzaRead`/`BitzaListRead` vs
  `bitza.model.ts`): missing `tags`, `low_stock_threshold`, `retired_at`,
  `retired_by_user_id`/`retired_by_display_name`, `parent_name`,
  `responsible_team_name`, `category_name`, `current_holder_display_name`,
  `purchased_by_display_name`, `child_count`, `is_checked_out`. Several of
  these (`child_count`, `is_checked_out`, the `*_name` fields) are exactly
  the kind of thing `BitzaBrowser`/the children table currently does
  client-side lookups for (`teamName()`, `categoryName()`) — the backend
  may already be doing this enrichment server-side, making some of that
  client-side lookup code redundant. Worth checking before assuming it's
  still needed.
- **`ReassignTeamResponse`** (`{bitza_id, team_id, cascade_scope,
  updated_count}`) is discarded entirely — `BitzaService.reassignTeam()`
  returns `Observable<void>`. `updated_count` would make a nice "N bitzas
  reassigned" confirmation instead of a silent success.
- **`BitzaImageRead`** actual fields: `uploaded_by`, `uploaded_by_display_name`,
  `uploaded_at`. The frontend's `BitzaImage` model has `filename` and
  `created_at` — **neither exists on the backend.** These were invented,
  not derived from anything. Harmless today only because `ImageGallery`
  never actually reads `.filename`/`.created_at` in code — but the model
  should be corrected regardless.
- **Category** (`CategoryRead` vs `category.model.ts`): missing
  `created_by`, `bitza_count`.
- **Team** (`TeamRead` vs `team.model.ts`): missing `member_count`.
- **`TeamMemberRead`** has its own `id` (the membership row's id, distinct
  from `user_id`/`team_id`) — not currently used for anything and routing
  doesn't need it (confirmed — see #4 above), but worth capturing for
  accuracy.
- **⏳ Still open.** **`BitzaFormDialog`'s "Stock tracking" dropdown is
  interactive but inert during edit.** The `stock_mode` `<mat-select>` is
  shown (and editable) whenever `kind === 'stock'`, regardless of
  `isEdit` — but the edit submit handler never includes `stock_mode` in
  the `BitzaUpdate` payload,
  correctly, since the backend has no such field there: `BitzaUpdate`'s
  own docstring says *"kind is intentionally NOT editable — converting a
  fixed location into a checkoutable tool (or vice versa) is a
  re-creation, not an update,"* and `stock_mode` is tied to `kind` the
  same way. An admin can flip the dropdown mid-edit, see no error, and
  reasonably believe they've changed how the stock is tracked — nothing
  actually changes on save. Not currently breaking anything (the rest of
  the edit still submits fine), but misleading. Found while fixing the
  `quantity` bug below; not fixed yet. Likely fix: disable the control
  (`[disabled]="isEdit"`) or hide it entirely on edit, matching the
  `kind`-is-readonly treatment already used just above it in the same
  form. **Note:** a new design question raised after this was logged
  ("New design questions raised" below, `kind` editability) may change
  what the right fix here actually is — if `kind` becomes genuinely
  editable, `stock_mode` needs to become properly editable alongside it
  rather than just disabled; read that section before implementing the
  "disable it" fix suggested above.

---

## Not a bug — an unexposed backend capability worth considering

**⏳ Still open — not started.**

`BitzaRepository.get_ancestors()` (a recursive CTE, used internally only
for `update_bitza`'s cycle-detection check) already computes exactly the
ancestor chain the frontend's breadcrumb needs — but there's no endpoint
exposing it. `BitzaBrowser`'s breadcrumb currently rebuilds this via N
sequential `GET /bitzas/{id}` calls (RxJS `expand`) walking `parent_id`
one hop at a time. If a lightweight `GET /bitzas/{id}/ancestors`-style
endpoint were added, the frontend could replace that with one call. Not
urgent, but a clean, low-risk win if this area gets touched anyway.

## New design questions raised — not yet decided, nothing built

Two things raised after reviewing the reconciliation work above. Neither
has been implemented. Both need a decision before work starts, not just
a fix — flagged here rather than as a "confirmed broken" item since
there's no bug, just a product/design call to make.

### A. Personal landing page (`/me`) — replace the root-bitza default

**The ask:** logging in currently drops you straight into the root of
the bitza tree (`''` → `bitzas` → root, via `redirectToRootGuard` in
`app.routes.ts`). That should instead default to a personal overview:
what you have checked out, what teams you're on.

This directly picks back up something `bitza_frontend_context.md`
explicitly logged as a deliberate scope cut: *"Cross-bitza checkout/
stock dashboards ('what's currently checked out' across the whole club,
'recent stock activity' feed) — nothing in the docs asked for this;
only per-bitza history exists."* It's being asked for now, scoped down
to a personal ("mine") slice rather than a club-wide feed.

**What it should show, concretely:**
1. **What you have checked out** — every bitza with an open Checkout
   row (`checked_in_at IS NULL`) held by you, across the *whole* tree,
   not scoped to one parent. Each row: bitza name/kind, when checked
   out, team_context/note, a link into that bitza, and ideally a
   check-in action right there — the whole point is not having to hunt
   through the tree to find something you already know you're holding.
2. **What teams you're on** — a simple list, each linking to
   `team-detail`. Lower-priority nice-to-have: highlighting which one
   is primary (see backend needs below — this needs a different query
   than "what teams," since primary is a membership-row property, not
   a team property).
3. Optional, not core: a one-line summary count at the top ("3 items
   checked out · 2 teams"); low-stock alerts for bitzas your teams are
   responsible for (ties into `low_stock_threshold`, which — per the
   completeness pass above — has no UI anywhere yet, on create, edit,
   *or* display, so this would be starting from zero, not just adding a
   dashboard tile); a "recent activity" feed — flagged with a caveat
   below, don't build this one without reading it first.

**Backend needs — this is the real work, not just a new frontend route:**

1. **A genuinely new endpoint is needed for "what I have checked out."**
   Nothing today supports it. The only checkout-listing endpoint,
   `GET /bitzas/{bitza_id}/checkouts`, is scoped to one bitza — there is
   no cross-tree "every open checkout held by user X" query anywhere in
   `checkout_repository.py` or `bitza_service.py`. Suggest something like
   `GET /checkouts/mine` (or `GET /users/me/checkouts`) doing a direct
   query against the Checkout table for `holder_id = current_user AND
   checked_in_at IS NULL`, with a **new response schema** — plain
   `CheckoutRead` doesn't carry the bitza's name/kind, and a list of bare
   `bitza_id`s isn't useful on its own without a follow-up call per row.
   Something like `{id, bitza_id, bitza_name, bitza_kind, team_context,
   note, checked_out_at}`.
2. **"What teams you're on" already works, mostly** —
   `GET /teams/?user_id={id}` exists (`TeamService.list(userId)` on the
   frontend already calls it) and returns `TeamListRead`
   (`id, name, member_count`). No backend change needed for the base
   version. If primary-team highlighting matters, that's a second,
   smaller possible addition — something like a
   `GET /users/me/team-memberships` returning `{team_id, team_name,
   is_primary}`, since "primary" lives on `TeamMember`, not `Team`, and
   there's currently no "my memberships across all teams" query either
   (only `GET /teams/{team_id}/members`, scoped to one team).
3. **If "recent activity" is wanted, don't reach for the audit log.**
   `GET /api/v1/audit/` is deliberately admin/superuser-gated — confirmed
   by a passing test (the same pattern as the directory-endpoint work
   above for `/users/`) — and that's a real privacy boundary someone
   made intentionally, not an oversight. A personal "recent activity"
   feed would need either a new self-scoped endpoint (mirroring the
   `/users/directory` precedent: a narrower, any-authenticated-user view
   rather than relaxing the admin gate) or deriving it from data you
   already have direct access to (your own checkout/stock-adjustment
   history), not from the audit trail. Worth deciding if this is even
   wanted before building anything here — it's the least load-bearing
   part of the ask.

**Routing:** add a new route (`/me` seems the obvious path) with its own
component; change the default (`''`) redirect target from `bitzas` to
`me`; leave the existing root-bitza browsing experience fully intact at
`/bitzas` behind a nav link, just no longer the first thing shown after
login.

### B. `kind` — should it be editable, and should it be called "type"?

**The ask:** `kind` is currently fixed at creation, never editable —
`BitzaUpdate`'s own docstring says so explicitly: *"kind is intentionally
NOT editable — converting a fixed location into a checkoutable tool (or
vice versa) is a re-creation, not an update."* The concern: mistakes will
happen, and locking it down entirely seems harsh. Separately: is "type" a
better user-facing label than "kind"?

**Why it's locked down today, and why that reasoning is real, not just
caution:** each `kind` carries genuinely different associated data —
`mobile` accumulates Checkout history, `stock` accumulates
`stock_mode`/`quantity`/`fuzzy_state` plus a StockLog history, `fixed`
has neither. Flipping `kind` on a bitza that already has history of the
"old" kind leaves that history semantically orphaned — what does an
existing Checkout row even mean once something's reclassified as
`stock`? That's the "re-creation, not an update" concern, and it's a
legitimate one, not an arbitrary restriction.

**But the concern behind the ask is just as real:**
`bitza_project_context.md` itself concedes `kind` is genuinely arbitrary
at the margins — *"a toolbox could equally be modelled as `mobile`...
the model doesn't force a choice here, it's just data"* — so early
misjudgment is expected, not user error. And the "just delete it and
start over" escape hatch closes fast: `delete_bitza` is blocked outright
once a bitza has **any** children (`child_count > 0`,
`bitza_service.py`), and since bitzas of any kind can have children
(kind is a classification, not a containment rule), a `fixed`-labelled
shelf that's had even one thing placed on it can no longer be deleted
and recreated to fix a kind mistake. That's often within the first real
use of the item, not some distant edge case.

**Recommendation: conditionally editable, not unconditionally editable.**
Rather than "always locked" vs. "always open," allow a `kind` change via
`PATCH` only when there's no history a kind change would orphan:
- Block a change away from `mobile` if the bitza has any Checkout rows.
- Block a change away from `stock` if it has any StockLog rows (a stock
  item that's only ever had `fuzzy_state` toggled — never an exact-mode
  adjustment — has no log rows, so that one's still safely switchable).
- A change *to* `stock` needs the same conditional-fields validation
  `BitzaCreate` already enforces (`stock_mode` required, `quantity`
  required if exact, etc.) — reuse that validator rather than
  duplicating it.
- A change away from `stock` should null out the now-irrelevant stock
  fields (`stock_mode`, `quantity`, `low_stock_threshold`,
  `fuzzy_state`).

This is a real feature, comparable in size to the exact-stock `quantity`
validation work already done, not a one-line unlock:
- **Backend:** `CheckoutRepository`/`StockLogRepository` currently only
  have `list_for_bitza` — need a count (or reuse `list_for_bitza` and
  check length; fine at this project's scale) to guard the change. New
  validation in `BitzaService.update_bitza`/`BitzaUpdate`. Given how
  consequential a kind change is, consider a dedicated audit log action
  for it (the audit system already exists and is keyed on
  `action`/`entity_type`, so this fits naturally).
- **Frontend:** re-enable the `kind` selector during edit (currently
  locked alongside `stock_mode`), surface *why* it's disabled when it is
  (e.g. "Can't change type: N checkouts on record"), and wire it into
  the update payload. This subsumes the still-open `stock_mode`-inert-
  during-edit item above — fix them together, since once `kind` can
  genuinely change, `stock_mode` needs real edit-time behavior anyway,
  not just a disable. Given the stakes, a confirmation dialog (matching
  the existing reassign-team/retire dialog pattern) seems warranted
  rather than a plain inline edit.

**On "type" vs "kind":** recommend relabelling in the **UI only** —
`<mat-label>`, table headers, filter text — not the underlying
TypeScript property name or the wire format. Keep `bitza.kind` as the
property name and the JSON key unchanged; just display "Type" instead of
"Kind" wherever it's currently labelled. Two concrete reasons not to
rename the field itself, not just caution:
1. `type` shadows Python's builtin `type()` — a standard reason Python
   codebases avoid it as a bare field/param name; `kind` reads like a
   deliberate choice for exactly this reason, not an accident.
2. There's already a different "type" concept in this same API: the
   audit log's `entity_type` (what *kind of record* was audited —
   `"bitza"`/`"team"`/`"user"`), which the audit log fix earlier in this
   doc surfaced in the UI as an "Entity" column. If `Bitza.kind` becomes
   user-facing "Type" while `entity_type` means something completely
   different, that's a collision waiting to confuse someone reading code
   and UI side by side later, even though the two would never appear on
   the same screen together.

Renaming the label only, keeping the model/wire name as `kind`, avoids
reintroducing exactly the class of frontend/backend field-name
disagreement this whole document was about fixing.

---

## Suggested approach for the new chat

The original 5-step plan here is done (schema reconciliation, the
completeness pass, and `bitza_frontend_context.md`'s assumptions section
— all patches `0001`–`0016`). For whoever picks this up next:

1. **Decide on the two new design questions above before building
   anything** — both need a product call (does `/me` need "recent
   activity"? is conditional-kind-editability the right shape, or is
   something simpler acceptable?), not just an implementation.
2. **If proceeding with `/me`:** backend first (the new checkout-by-user
   endpoint is the one genuinely new piece), then the frontend route +
   component + default-redirect change.
3. **If proceeding with `kind` editability:** backend validation first
   (the history-guard + reused conditional-fields validator), then the
   frontend edit-form changes — and fix the already-logged
   `stock_mode`-inert-during-edit bug as part of the same pass, not
   separately, since they're now the same piece of work.
4. **`get_ancestors`** is still just sitting there as a low-risk win if
   either of the above ends up touching `bitza-browser.ts`'s breadcrumb
   anyway.
5. **Still no live click-through against a running backend+frontend
   together** — every fix in this whole document was verified via
   `ng test`/`ng build`/`pytest`/`mypy` plus careful reading, not an
   actual HTTP round trip. That remains the single biggest source of
   residual risk across everything done so far.
