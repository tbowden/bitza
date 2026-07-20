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
