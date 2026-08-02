/**
 * Formerly called `Team` throughout the frontend too, until Stage 5 renamed
 * only the *display label* to "Project" while the backend (and this file)
 * kept saying "Team" underneath. Stage 6 brought the backend into line —
 * see bitza_open_issues.md — so this is now just "Project", top to bottom.
 */
export interface Project {
  id: string;
  name: string;
  description?: string | null;
  /** Populated by the service. */
  member_count: number;
  created_at: string;
}

/**
 * The compact shape GET /projects/ actually returns (`ProjectListRead`) — no
 * description or created_at at all, unlike `Project` (`ProjectRead`, from
 * GET /projects/{id}). ProjectService.list() used to be typed as Project[],
 * which claimed a description field the list endpoint never returns —
 * see projects-list.ts, where that silently broke the card description.
 */
export interface ProjectListItem {
  id: string;
  name: string;
  member_count: number;
}

export interface ProjectCreate {
  name: string;
  description?: string | null;
}

export interface ProjectUpdate {
  name?: string;
  description?: string | null;
}

/**
 * Plain many-to-many join, no history (see "Membership" in
 * bitza_project_context.md). `is_primary` carries no permission meaning —
 * it only pre-fills `project_context` at checkout time.
 */
export interface ProjectMember {
  /** The membership row's own id — distinct from user_id/project_id. Not currently used for routing (mutations key off user_id — see ProjectService). */
  id: string;
  user_id: string;
  project_id: string;
  is_primary: boolean;
  /** Always populated by the backend service — never a raw fallback. */
  user_display_name: string;
}

export interface ProjectMemberCreate {
  user_id: string;
  is_primary?: boolean;
}

/**
 * One row of GET /projects/mine — the current user's own memberships,
 * project name plus is_primary in one call. Distinct from `ProjectListItem`
 * (GET /projects/?user_id=): that shape is built for browsing any user's
 * projects and omits is_primary entirely, since primary-ness is only
 * meaningful for the current user's own checkout defaults.
 */
export interface MyProjectMembership {
  project_id: string;
  project_name: string;
  is_primary: boolean;
}
