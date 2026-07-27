# Bitza — frontend/backend schema reconciliation

**Read this first if you're picking up this specific task.** For full
project orientation, see `bitza_context_restoration.md`; for frontend
architecture generally, see `bitza_frontend_context.md`. This document is
scoped narrowly to one problem: the Angular frontend was built from
`bitza_project_context.md`'s prose description of the API, not from the
live backend schemas — and in several places, reality and the docs
(and therefore the frontend) have drifted apart. This is not a
speculative concern; every item below was confirmed by reading the actual
`backend/app/schemas/*.py` files directly against the frontend's
`frontend/bitza/src/app/core/models/*.ts` files.

Auth (`schemas/auth.py`) was checked and has **no** drift — Phase 1's
contract is accurate and unchanged. Everything below is Team/Bitza-model
territory (Stage 2 onward).

---

## Confirmed likely-broken — fix these first

These aren't missing nice-to-haves. Each one is a field-name or polarity
mismatch between what the backend actually sends/expects and what the
frontend reads/sends. None of this has had a live click-through against a
real backend yet (see `bitza_frontend_context.md`'s "Stage 3 caveats"), so
these are confirmed by reading source on both sides, not confirmed by
reproducing the failure — worth actually running the two together to
verify before/after any fix.

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

These are real gaps (backend sends more than the frontend models capture,
or a frontend field is outright invented and doesn't exist backend-side),
but nothing currently reads the missing/wrong fields, so there's no live
breakage — just data that could improve the UI if surfaced, or a model
that should be corrected for accuracy even though it hasn't bitten yet.

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
- **`BitzaFormDialog`'s "Stock tracking" dropdown is interactive but inert
  during edit.** The `stock_mode` `<mat-select>` is shown (and editable)
  whenever `kind === 'stock'`, regardless of `isEdit` — but the edit
  submit handler never includes `stock_mode` in the `BitzaUpdate` payload,
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
  form.

---

## Not a bug — an unexposed backend capability worth considering

`BitzaRepository.get_ancestors()` (a recursive CTE, used internally only
for `update_bitza`'s cycle-detection check) already computes exactly the
ancestor chain the frontend's breadcrumb needs — but there's no endpoint
exposing it. `BitzaBrowser`'s breadcrumb currently rebuilds this via N
sequential `GET /bitzas/{id}` calls (RxJS `expand`) walking `parent_id`
one hop at a time. If a lightweight `GET /bitzas/{id}/ancestors`-style
endpoint were added, the frontend could replace that with one call. Not
urgent, but a clean, low-risk win if this area gets touched anyway.

---

## Suggested approach for the new chat

1. **Fix the five confirmed-broken items first** (Create User, Suspend,
   Checkout holder, Team member display, Audit log description) — these
   affect already-shipped Milestones 2, 4, and 5. Each fix is: correct
   the frontend model's field name(s)/type, update whatever component(s)
   read that field, and — for Checkout/Audit specifically — check whether
   the backend's own `*_display_name` enrichment makes the frontend's
   batched `UserService.get()` lookup code unnecessary, and remove it if so.
2. **Then work through the "confirmed missing" list** entity by entity,
   deciding for each field: surface it in the UI, or explicitly skip it
   and note why (not every extra field needs a home in the UI).
3. **Verify as you go against a real, running backend** if at all
   possible — every finding above came from reading source side-by-side,
   not from an actual failing request/response observed in practice. That
   would be a stronger signal than source-reading alone, and this project
   hasn't had that live verification yet at all.
4. Consider the `get_ancestors` endpoint addition once the above is settled.
5. Update `bitza_frontend_context.md`'s "Assumptions needing backend
   confirmation" section once done — several of those listed items are
   now *more* than assumptions (confirmed wrong, specifically), and this
   document should be considered closed/archived once the fixes land.
