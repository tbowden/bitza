export interface AuditLogEntry {
  id: string;
  action: string;
  summary: string;
  user_id: string;
  created_at: string;
}

export interface AuditListParams {
  user_id?: string;
  action?: string;
}
