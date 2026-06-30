# Bitza — project context

Project-specific decisions and contracts for the Bitza asset management app.
Use this document alongside the general FastAPI and Angular context instructions.
It covers things that are specific to this project rather than general tooling patterns.

---

## What Bitza is

A full-stack app for tracking the location and quantity of physical assets —
electronic components, tools, and miscellaneous items stored across named
locations in a home or workshop. The name comes from "bitza this and bitza that".

Stack:
- **Backend** — FastAPI + SQLite, `bitza/backend/`
- **Frontend** — Angular, `bitza/frontend/`

---

## Auth contract (backend → frontend)

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

The backend enforces:
- Minimum 12 characters, maximum 128
- zxcvbn score ≥ 3

The frontend should provide **advisory** real-time feedback using the
`zxcvbn` npm package (not a blocking gate — the backend is authoritative).
Show a strength indicator as the user types. Do not block form submission
on the frontend strength check alone; let the backend return a 422 if the
password fails.

Use the npm package `zxcvbn` for consistency with the backend implementation.
Check for a maintained fork if the original package appears unmaintained at
the time of implementation.

---

## Location privacy (frontend behaviour)

The API filters all location and asset lists server-side based on the current
user's visibility. The frontend does not need to implement any privacy logic.

Key behaviours to be aware of:

**Lists are pre-filtered.** `GET /api/v1/locations/` only returns locations
the current user can see. If a location is private and the user doesn't own
it, it simply won't appear in the list.

**404 means "not found or not visible".** The backend intentionally returns
404 (not 403) for resources the user can't see, to avoid revealing that
something exists. The Angular app should treat all 404s as "not found" without
trying to distinguish between the two cases.

**Superuser sees everything.** Admins respect privacy rules the same as
normal users — only the superuser bypasses all privacy. This affects what
admin-role users see in the UI.

---

## Two-level location picker

When creating or editing an asset, the location is chosen in two steps:

1. **Storage location** — top-level room or area (e.g. "James' room",
   "Dad's carport"). Fetched from `GET /api/v1/locations/`.

2. **Location detail** — sub-location within the chosen storage location
   (e.g. "Box 3", "Top shelf"). Fetched from
   `GET /api/v1/locations/{id}/details` after a storage location is selected.

This is a dependent dropdown: the detail dropdown is empty and disabled until
a storage location is chosen, then populated by a second API call. The asset
form must send `location_detail_id` (not `location_id`) — the detail ID is
what gets stored on the asset.

Both endpoints return only what the current user can see, so the dropdowns
are naturally privacy-filtered without any frontend logic.

---

## File upload (asset image)

The image upload endpoint uses `multipart/form-data`, not JSON. This is the
only endpoint in the API that isn't JSON — all others use
`Content-Type: application/json`.

```
POST /api/v1/assets/{id}/image
Content-Type: multipart/form-data

file: <binary image data>
```

Use Angular's `HttpClient` with a `FormData` object. Do not set the
`Content-Type` header manually — let the browser set it with the boundary
string automatically.

Accepted types: JPEG, PNG, GIF, WebP. Maximum size: 10 MB.
The response is the full updated asset object.

---

## User roles (what the UI needs to know)

Three roles: `superuser`, `admin`, `user`. The current user's role is
available in the `GET /api/v1/users/me` response.

| What to show/hide | superuser | admin | user |
|---|---|---|---|
| User management section | ✓ | ✓ | ✗ |
| Create admin option in user form | ✓ | ✗ | ✗ |
| Role change controls | ✓ | ✗ | ✗ |
| Suspend / delete controls | ✓ | users only | ✗ |
| Audit log | ✓ | ✓ | ✗ |
| Category management | ✓ | ✓ | ✓ |

The backend enforces all permissions — the frontend role checks are purely
for showing and hiding UI elements. Never rely on frontend role checks for
security.

---

## API base URL and versioning

All endpoints are prefixed with `/api/v1/`. Define this as an environment
variable in the Angular project:

```
# environments/environment.ts
apiUrl: 'http://localhost:8000/api/v1'

# environments/environment.prod.ts
apiUrl: 'https://<your-domain>/api/v1'
```

The health check endpoint (`/health`) is at the root, not under `/api/v1/`.

---

## Stock transactions

Quantity is never edited directly on an asset. All quantity changes go through
the transaction endpoint:

```
POST /api/v1/assets/{id}/transactions
{"delta": 5, "note": "Restocked from Aliexpress order"}   // stock in
{"delta": -2, "note": "Used in weather station project"}  // stock out
```

The backend rejects transactions that would make quantity negative. The UI
should show the current quantity and make it clear whether a delta is adding
or removing stock (e.g. with a +/- toggle rather than a signed number input).

---

## Image serving

Asset images are served via an authenticated endpoint — not as static files.
This means the same privacy rules that govern asset visibility also govern
image visibility. If you cannot see the asset, you cannot see its image.

```
GET /api/v1/assets/{id}/image
Authorization: Bearer <access_token>

→ image/jpeg (or image/png, image/gif, image/webp)
```

Returns 404 if the asset is not found, not visible to the current user,
has no image attached, or the file is missing from disk.

### Angular implementation

Browsers do not send `Authorization` headers with plain `<img>` tags, so this
pattern **will not work**:

```html
<!-- DO NOT DO THIS — no auth header will be sent -->
<img [src]="'/api/v1/assets/' + asset.id + '/image'">
```

Instead, fetch the image via `HttpClient` with `responseType: 'blob'` and
create a temporary object URL:

```typescript
// In your component
imageUrl: string | null = null;

loadImage(assetId: string): void {
  this.http
    .get(`/api/v1/assets/${assetId}/image`, { responseType: 'blob' })
    .subscribe({
      next: (blob) => {
        // Revoke previous URL to avoid memory leaks
        if (this.imageUrl) URL.revokeObjectURL(this.imageUrl);
        this.imageUrl = URL.createObjectURL(blob);
      },
      error: (err) => {
        if (err.status === 404) this.imageUrl = null; // no image set
      },
    });
}

ngOnDestroy(): void {
  if (this.imageUrl) URL.revokeObjectURL(this.imageUrl);
}
```

```html
<img *ngIf="imageUrl" [src]="imageUrl" alt="Asset image">
```

`URL.revokeObjectURL()` must be called when the component is destroyed to
release the memory held by the blob URL. If you forget this, every image
load leaks memory for the lifetime of the browser tab.

---

## Known decisions still to be made

These are open questions that will need answering when frontend work begins:

- **Token refresh strategy** — interceptor-based (transparent to the rest of
  the app) vs explicit refresh calls. Interceptor is strongly recommended.
- **Session persistence** — does the app stay logged in across browser
  restarts? (Yes if using localStorage, no if sessionStorage.)
- **Offline behaviour** — out of scope for now but worth noting that SQLite
  backend has no sync capability.
