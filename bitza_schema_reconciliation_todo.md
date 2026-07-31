# Bitza — frontend/backend schema reconciliation

**Status: COMPLETE.** 16 patches (`0001`–`0016`), applied and pushed.
Everything in "Confirmed likely-broken" and "Confirmed missing but
harmless" is resolved. The two follow-on items this doc originally left
open — the inert `stock_mode` dropdown and the unexposed `get_ancestors`
capability — are also both done now (see "Not a bug" section below for
`get_ancestors`; the `stock_mode` fix was folded into and then superseded
by the `kind` editability work described next). The two new design
questions raised after review — a personal `/me` landing page, and `kind`
editability/labelling — are **both built**, tested, applied, and pushed;
see "New design questions raised" below, now updated to reflect what
shipped for each.

**This entire document is historical record at this point — nothing here
is outstanding work.** If you're picking up fresh work on this project,
go straight to `bitza_open_issues.md` instead, which covers what came out
of this doc's completion (four new items: login landing page, root bitza
lockdown, stock-can't-have-children, and settling the Team/Project naming
question).

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

**✅ Fully resolved.** Patches `0010`–`0016`. Two real, live bugs were found *while*
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
- **✅ Resolved — superseded by `kind` editability.** **`BitzaFormDialog`'s
  "Stock tracking" dropdown was interactive but inert during edit.** The
  `stock_mode` `<mat-select>` was shown (and editable) whenever
  `kind === 'stock'`, regardless of `isEdit`, but the edit submit handler
  never included `stock_mode` in the `BitzaUpdate` payload — an admin
  could flip the dropdown mid-edit, see no error, and reasonably believe
  they'd changed how the stock was tracked, with nothing actually
  changing on save. Fixed in two stages: first a quick "hide it entirely
  on edit, matching the `kind`-is-readonly treatment" patch (matching
  what this section originally suggested), then fully superseded by the
  `kind` editability work below — `stock_mode` is now genuinely editable
  (independently of `kind`), gated by the same checkout/stock-log history
  guards, with the frontend locking the control and explaining why only
  when there's real history to protect. See "New design questions
  raised" → B below for what actually shipped.

---

## Not a bug — an unexposed backend capability worth considering

**✅ Resolved.**

`BitzaRepository.get_ancestors()` (a recursive CTE, previously used
internally only for `update_bitza`'s cycle-detection check) already
computed exactly the ancestor chain the frontend's breadcrumb needs — it
just wasn't exposed as an endpoint. Now it is:
`GET /bitzas/{id}/ancestors` (nearest parent first, root last, excludes
the bitza itself). `BitzaBrowser`'s breadcrumb no longer rebuilds this via
N sequential `GET /bitzas/{id}` calls (the old RxJS `expand` walk) — one
call now.

## New design questions raised — both now decided and built

Two things raised after reviewing the reconciliation work above. Both
needed a decision before work started, not just a fix — kept here rather
than as a "confirmed broken" item since there was no bug, just a
product/design call to make. Both are now built; each subsection below
has been updated with a resolution note at the top.

### A. Personal landing page (`/me`) — replace the root-bitza default

**✅ Built.** `GET /checkouts/mine` (top-level resource, not nested under
`/bitzas/{id}` — scoped to a holder across the whole tree, not to one
bitza) and `GET /teams/mine` (team name + `is_primary` in one call) were
added, plus a `/me` route and `MePage` component: "checked out to you"
(with a check-in action reusing the existing `CheckinDialog`) and
"{{ Teams }} you're on" (primary starred). Low-stock alerts and a "recent
activity" feed were both explicitly left out, as flagged below — neither
was decided as wanted, and low-stock alerts really would have been
starting from zero.

**⚠️ One thing from this section's own routing note did *not* actually
ship:** "change the default (`''`) redirect target from `bitzas` to
`me`" was never done — `/me` was added as a new route and nav link, but
the app still lands on `/bitzas` after login. That gap is now
`bitza_open_issues.md`'s issue #1.

**The ask, as originally written, for reference:** logging in currently drops you straight into the root of
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

**✅ Built, following the recommendation below almost exactly.**
`kind`/`stock_mode` are now conditionally editable via `PATCH` —
checkout-history guard for moving away from `mobile`, stock-log-history
guard for moving away from `stock_mode='exact'` (whether to a different
`kind` or just to `fuzzy`), the reused `BitzaCreate`-style validation for
moving *to* `stock`, and a dedicated `CHANGE_KIND` audit action (not
folded into the generic `UPDATE` entry). Frontend re-enables the
`kind`/`stock_mode` selectors during edit, locks them with a reason when
there's real history to protect (e.g. "locked — 3 checkouts on record"),
and shows a confirmation dialog before an actual transition submits.
Labelling was changed to "Type" in UI text only, exactly as recommended —
`bitza.kind` is unchanged as the property name and wire format.

**One gap the recommendation below didn't anticipate, found writing this
up:** none of this checks whether a bitza already **has children** before
letting its `kind` move *to* `stock` — and since stock bitzas shouldn't be
able to have children at all (a separate, newly-raised rule), that's now
its own item: `bitza_open_issues.md`'s issue #3.

**The ask, as originally written, for reference:** `kind` is currently fixed at creation, never editable —
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

Everything in this document — the original 5-step plan (schema
reconciliation, the completeness pass, `bitza_frontend_context.md`'s
assumptions section), the `stock_mode` and `get_ancestors` follow-ons,
and both design questions above — is done, tested, applied, and pushed.

**For whoever picks this up next: go to `bitza_open_issues.md`.** It
covers what came out of finishing this doc — a login-redirect gap this
doc's own routing note called for but that didn't ship, a root-bitza
lockdown, a stock-bitzas-can't-have-children rule, and settling the
Team/Project naming question for good.

The one thing worth repeating here since it still applies project-wide:
**there is still no live click-through against a running backend+frontend
together.** Every fix in this whole document, and everything built for
the two design questions above, was verified via `ng test`/`ng
build`/`pytest` plus careful reading, not an actual HTTP round trip. That
remains the single biggest source of residual risk across everything
done so far.
