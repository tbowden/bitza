/**
 * `Team` doubles as "Project" in the frontend's own display labelling only
 * (see AppConfigService) — nothing in the API encodes that distinction.
 */
export interface Team {
  id: string;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface TeamCreate {
  name: string;
  description?: string | null;
}

export interface TeamUpdate {
  name?: string;
  description?: string | null;
}

/**
 * Plain many-to-many join, no history (see "Membership" in
 * bitza_project_context.md). `is_primary` carries no permission meaning —
 * it only pre-fills `team_context` at checkout time.
 */
export interface TeamMember {
  user_id: string;
  team_id: string;
  is_primary: boolean;
  /** Always populated by the backend service — never a raw fallback. */
  user_display_name: string;
}

export interface TeamMemberCreate {
  user_id: string;
  is_primary?: boolean;
}
