/** Matches backend AuditLogRead (schemas/audit.py) exactly. */
export interface AuditLogEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  /** Nullable — some audit actions aren't attributable to a user. */
  user_id: string | null;
  /** Always populated by the backend service — never a raw fallback. */
  user_display_name: string;
  description: string | null;
  created_at: string;
}

/**
 * GET /api/v1/audit/ only supports these three query params (see
 * endpoints/audit.py) — there is no server-side filter by user or
 * action text. The UI filters by those locally instead; see AuditLog.
 */
export interface AuditListParams {
  entity_type?: string;
  entity_id?: string;
  limit?: number;
}
