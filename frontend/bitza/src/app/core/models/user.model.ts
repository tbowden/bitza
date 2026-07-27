/**
 * Roles govern account management only (see "User roles" in
 * bitza_project_context.md) — they have no bearing on the Team/Bitza
 * trust model except gating hard-delete of a bitza and the audit log.
 */
export type UserRole = 'superuser' | 'admin' | 'user';

export interface User {
  id: string;
  email: string;
  username: string;
  display_name: string;
  role: UserRole;
  /**
   * Backend polarity (`UserRead.is_active`): true = can sign in, false =
   * suspended. This is the *opposite* sense of the old `is_suspended`
   * field this replaces — see AdminUserUpdate below.
   */
  is_active: boolean;
  created_at: string;
}

/**
 * GET /users/directory — id + display_name only, no email/role/is_active.
 * Any authenticated user may call this (unlike `list()`/`GET /users/`,
 * which is genuinely admin/superuser-only — confirmed against
 * UserService.list_users's permission matrix in the backend, and by a
 * passing test asserting a 403 for a plain user). This exists
 * specifically to power pickers like the team add-member dialog.
 */
export interface UserDirectoryEntry {
  id: string;
  display_name: string;
}

/** Payload for PATCH /users/me and admin-gated user edits. */
export interface UserUpdate {
  email?: string;
  username?: string;
  password?: string;
}

/**
 * Admin-only user management. The docs confirm `/api/v1/users/` CRUD is
 * admin/superuser-gated and describe the permission *table* (who can see
 * role controls, create-admin, suspend/delete) but not the exact request
 * shapes for create/suspend — these are the natural REST shapes given
 * everything else in the app, flagged here in case the backend differs.
 *
 * `display_name` is REQUIRED by the backend (`schemas/user.py`,
 * min_length=1) — distinct from `username` (the login handle). Omitting
 * it is why user creation was completely broken: every submission got
 * rejected with a 422 the UI never explained.
 */
export interface UserCreate {
  email: string;
  username: string;
  display_name: string;
  password: string;
  role: UserRole;
}

/**
 * Matches backend `UserUpdate` — a plain PATCH, admin/superuser-gated.
 * `is_active` (not `is_suspended`) is the backend's actual field: true =
 * active/can sign in, false = suspended. To suspend, send
 * `is_active: false`; to unsuspend, send `is_active: true` — i.e. always
 * the *opposite* of the user's current `is_active`, not of some
 * `is_suspended` flag that doesn't exist on the wire.
 */
export interface AdminUserUpdate {
  display_name?: string;
  email?: string;
  username?: string;
  role?: UserRole;
  is_active?: boolean;
}
