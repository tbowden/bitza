# Bitza — open issues (post-reconciliation)

**Status: not started.** Raised after `bitza_schema_reconciliation_todo.md` was
fully completed — 16 patches plus both design questions it raised (`/me`
landing page, `kind` editability/labelling) are built, tested, applied, and
pushed to `main`. Read `bitza_context_restoration.md` first if you haven't —
it explains the overall project stage and links everything else.

Three of these are straightforward backend+frontend fixes (#1–#3). The
fourth (#4) is a **decided** naming question — nothing left to weigh, just
implementation.

---

## 1. Login should land on `/me`, not `/bitzas`

**Current behaviour:** after successful login, the app navigates to `/`
(`features/auth/login/login.ts`), which redirects to `bitzas`
(`app.routes.ts`'s `{ path: '', redirectTo: 'bitzas', pathMatch: 'full' }`),
which itself redirects to the root bitza's detail page via
`redirectToRootGuard`.

**Fix:** one line.

```ts
// app.routes.ts
{ path: '', redirectTo: 'bitzas', pathMatch: 'full' },   // → redirectTo: 'me'
```

**Worth a look while you're in there:** a fresh, not-yet-bootstrapped
deployment (no root bitza created via the CLI yet) currently falls through
`redirectToRootGuard` to `BitzaBrowser`'s own "not set up yet" message. Once
the default lands on `/me` instead, that message won't be the first thing a
fresh admin sees — `/me` will just show empty "nothing checked out" / "not
on any Projects" states instead, which doesn't clearly say the *system*
isn't bootstrapped yet. Not blocking; worth a decision (give `/me` a similar
empty/setup state, or accept the gap since an admin can just visit `/bitzas`
directly).

---

## 2. Root bitza should be locked down — name-only, admin-only

**Already protected (`bitza_service.py`):** the root bitza (the one tracked
in `SystemConfig.root_bitza_id`) can't be **deleted**, **retired**, or
**moved** (`parent_id` change) — all three raise `RootBitzaProtectedError`
(409) unconditionally, regardless of role. See `update_bitza`,
`delete_bitza`, `retire_bitza`.

**What's missing:** ordinary field edits via `PATCH /bitzas/{id}` are not
guarded for the root at all. `name`, `description`, `category_id`,
`responsible_team_id`, `tags`, `vendor`, `purchase_date`, `order_url`, and
— since the `kind` editability work — `kind`/`stock_mode`/`quantity`/
`fuzzy_state`/`low_stock_threshold` can currently all be changed on the
root by any authenticated user. This became a *live* risk specifically
because of kind editability — before that patch, `kind` was immutable for
every bitza including root, so this gap had no way to actually bite yet.

**Requested behaviour:** the root bitza should only ever have its `name`
changed, and only by an admin (or superuser). Every other field should be
rejected outright.

**Suggested approach:**

- In `update_bitza`, alongside the existing `bitza_id == root_bitza_id`
  check for `parent_id`, add a root-specific branch: if this bitza is the
  root, only `name` may be present in the payload at all — reject the
  *whole* request (not a partial-apply) if anything else is set, and
  require `actor.role in (admin, superuser)` even for the `name` change
  (mirrors the check already in `delete_bitza`).
- Decide the error split: a non-admin touching `name` is probably
  `PermissionDeniedError` (403); any other field being present is
  `RootBitzaProtectedError` (409), matching the existing unconditional
  delete/retire/move protection. If both are true at once (non-admin *and*
  non-name fields), which wins is a minor call — 403 is probably the more
  useful answer, but either is defensible.
- No separate "kind must stay fixed" check is needed beyond "nothing but
  `name` is editable at all" — the root is always created with
  `kind='fixed'` (`create_root_bitza`) and this same guard is what keeps it
  that way now that `kind` is generally PATCH-able.
- Frontend: `BitzaFormDialog` should reflect this when editing the root —
  probably hide/disable every field but `name` (same pattern already used
  for the conditionally-editable `kind`/`stock_mode` fields), and only let
  a non-admin open the dialog read-only or not at all. `bitza.is_root` is
  already on `BitzaListRead`/`BitzaRead` for detecting this client-side —
  as always in this app, the backend guard is the real authority and the
  frontend change is purely for a better, error-free experience.

---

## 3. Stock bitzas should never have children

**Current behaviour:** nothing enforces this anywhere. `create_bitza` never
checks the parent's `kind` — a stock bitza can be given children today via
`POST /bitzas/` with `parent_id` pointing at it. Same gap in
`update_bitza`'s `parent_id`-change path (moving a bitza under a stock
parent). And, from the recent kind-editability work, in the kind-transition
block itself: changing a `fixed`/`mobile` bitza's kind *to* `stock` doesn't
check whether it already has children.

**Frontend:** `BitzaBrowser`'s "Add here" button (per-bitza card actions) is
shown unconditionally regardless of the current bitza's `kind` — no
client-side signal exists yet that this shouldn't be offered under a stock
item.

**Suggested approach:**

- Backend, three call sites in `bitza_service.py`:
  1. `create_bitza` — after resolving `data.parent_id`'s bitza, reject
     with `ConflictError` (409) if its `kind == BitzaKind.stock`.
  2. `update_bitza`'s `parent_id`-change branch — same check against the
     new parent.
  3. The kind-transition block (kind editability) — when transitioning
     *to* `stock`, reject if `self._bitzas.count_children(bitza_id) > 0`
     (the same `count_children` method `delete_bitza` already uses).
- A small shared helper (e.g. `_reject_if_parent_is_stock(parent)`) called
  from (1) and (2) avoids duplicating the check/message.
- Frontend: hide "Add here" in `BitzaBrowser` when the bitza being viewed
  (the prospective parent) has `kind === 'stock'` — same cheap
  kind-conditional-UI pattern used elsewhere.
- Worth a test for all three paths. No data-migration concern — nothing
  has ever allowed a stock item to have children, so this is a pure
  validation gap, not a data-repair job.

---

## 4. Settle on "Project" — remove the Team/Project ambiguity

**Decided** — see `bitza_project_context.md`'s "Team vs Project label"
section (updated to reflect this). The product will always call it
"Project" in the UI. The backend/API stays named `Team` throughout (table,
model, field names like `responsible_team_id`, endpoint paths like
`/api/v1/teams/`) — still purely a **display-label** decision, same as the
original framing. Nothing about the schema or wire format changes.

**Current implementation:** `AppConfigService`
(`core/services/app-config.service.ts`) holds this as a runtime signal
(`'team' | 'project'`), defaulting to `'team'`, persisted to `localStorage`,
with no settings screen anywhere to actually change it. `teamLabelSingular()`
/ `teamLabelPlural()` are consumed in 8 components plus the service itself
and a comment in `team.model.ts`: `teams-list.ts`, `team-form-dialog.ts`,
`team-detail.ts`, `me-page.ts`, `bitza-browser.ts`,
`reassign-team-dialog.ts`, `bitza-form-dialog.ts`, `app-shell.ts`.

**Suggested approach — recommend removing the toggle, not just flipping its
default:** the decision is now permanent rather than deployment-configurable,
so a whole runtime/localStorage-backed toggle for a resolved question is
unneeded complexity going forward. Recommend:

- Delete `AppConfigService` (or gut it, if the injection token turns out to
  be depended on elsewhere) and its `.spec.ts`.
- Replace every `config.teamLabelSingular()` / `config.teamLabelPlural()`
  call site with the literal strings `'Project'` / `'Projects'` (or a small
  shared constant, if that reads better — a style call, not a design one).
- Update the stale `AppConfigService` reference in the `team.model.ts`
  comment.
- If keeping some flexibility for a hypothetical future settings screen is
  preferred over a full rip-out, the minimal alternative is just flipping
  the default from `'team'` to `'project'` and leaving the toggle
  infrastructure in place. Flag this choice if it's not obvious which is
  wanted — simplicity now vs. optionality later is a real trade-off, not a
  purely mechanical one.
- No backend changes, no schema changes. No new tests needed beyond
  anything that currently asserts on the literal word "Team" in rendered
  text — unlikely, since no component-level tests exist yet (see
  `bitza_frontend_context.md`'s Testing state section).

---

## Suggested approach for the new chat

All four are independent — no ordering dependency — but #2 and #3 both
touch `update_bitza`'s kind-transition block (from the just-completed kind
editability work), so doing them in the same backend pass is efficient. #1
and #4 are frontend-only and much smaller.

1. Read this doc, then re-confirm current `main` (`git log --oneline -5`) —
   written against the tip right after kind editability shipped; re-check
   the relevant files if anything's changed since.
2. Backend: #2 (root lockdown) and #3 (stock-can't-have-children) together
   in `bitza_service.py`, with tests.
3. Frontend: #2 and #3's client-side reflections in
   `BitzaFormDialog`/`BitzaBrowser`.
4. #1 (login redirect) — trivial, do whenever.
5. #4 (Team → Project) — mechanical, touches many files but low risk; good
   as its own focused pass since it touches nearly every team-related
   component.
