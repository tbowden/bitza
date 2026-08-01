/**
 * `Team` is always displayed as "Project" in the frontend — a permanent
 * display-label decision (see bitza_project_context.md's "Team vs Project
 * label" section), not encoded anywhere in the API.
 */
export interface Team {
  id: string;
  name: string;
  description?: string | null;
  /** Populated by the service. */
  member_count: number;
  created_at: string;
}

/**
 * The compact shape GET /teams/ actually returns (`TeamListRead`) — no
 * description or created_at at all, unlike `Team` (`TeamRead`, from
 * GET /teams/{id}). TeamService.list() used to be typed as Team[],
 * which claimed a description field the list endpoint never returns —
 * see teams-list.ts, where that silently broke the card description.
 */
export interface TeamListItem {
  id: string;
  name: string;
  member_count: number;
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
  /** The membership row's own id — distinct from user_id/team_id. Not currently used for routing (mutations key off user_id — see TeamService). */
  id: string;
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

/**
 * One row of GET /teams/mine — the current user's own memberships,
 * team name plus is_primary in one call. Distinct from `TeamListItem`
 * (GET /teams/?user_id=): that shape is built for browsing any user's
 * teams and omits is_primary entirely, since primary-ness is only
 * meaningful for the current user's own checkout defaults.
 */
export interface MyTeamMembership {
  team_id: string;
  team_name: string;
  is_primary: boolean;
}
