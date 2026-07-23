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
  role: UserRole;
  is_suspended: boolean;
  created_at: string;
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
 */
export interface UserCreate {
  email: string;
  username: string;
  password: string;
  role: UserRole;
}

/**
 * Modelled as a plain PATCH including `is_suspended`, matching the rest
 * of the app's style (e.g. fuzzy_state) rather than a dedicated
 * suspend/unsuspend endpoint — flagged as an assumption, not confirmed
 * against a documented endpoint shape.
 */
export interface AdminUserUpdate {
  email?: string;
  username?: string;
  role?: UserRole;
  is_suspended?: boolean;
}
