/**
 * The one axis that actually distinguishes a shelf from a toolbox from a
 * multimeter — see "Bitzas — the unified location/container/item model".
 */
export type BitzaKind = 'fixed' | 'mobile' | 'stock';

export type BitzaStatus = 'active' | 'retired';

export type RetiredReason = 'lost' | 'broken' | 'discontinued' | 'superseded';

export type StockMode = 'exact' | 'fuzzy';

export type FuzzyState = 'plentiful' | 'low' | 'empty';

/**
 * `cascade_scope` heuristics for the reassign-team dialog are a frontend
 * UX default only (see "Reassigning responsible team") — this type documents
 * the three legal values, not a suggestion of which to default to.
 */
export type CascadeScope = 'none' | 'direct_children' | 'all_descendants';

export interface Bitza {
  id: string;
  name: string;
  kind: BitzaKind;
  parent_id: string | null;
  /** Populated by the service — null only for the root bitza. */
  parent_name: string | null;
  responsible_team_id: string;
  /** Populated by the service. */
  responsible_team_name: string;
  status: BitzaStatus;
  /**
   * True for exactly one bitza system-wide — the tree's single, permanent
   * anchor. Computed by the backend (not a stored flag on every row — see
   * bitza_frontend_context.md / the backend's SystemConfig model). Used
   * to hide retire/delete/move actions the backend will reject anyway.
   */
  is_root: boolean;
  retired_reason: RetiredReason | null;
  retired_note: string | null;
  retired_at: string | null;
  retired_by_user_id: string | null;
  /** Populated by the service. */
  retired_by_display_name: string | null;
  category_id: string | null;
  /** Populated by the service. */
  category_name: string | null;
  tags: string[] | null;
  description?: string | null;

  /** Number of direct children — populated by the service. */
  child_count: number;

  // stock (kind = 'stock') only
  stock_mode?: StockMode | null;
  quantity?: number | null;
  low_stock_threshold?: number | null;
  fuzzy_state?: FuzzyState | null;

  // acquisition / provenance
  purchased_by_user_id?: string | null;
  /** Populated by the service. */
  purchased_by_display_name: string;
  vendor?: string | null;
  purchase_date?: string | null;
  order_url?: string | null;

  /**
   * kind = 'mobile' only — derived from the newest Checkout row with
   * checked_in_at === null, never a stored flag. See Checkout.model.ts.
   */
  is_checked_out: boolean;
  /** Populated by the service. */
  current_holder_display_name: string | null;

  created_at: string;
  updated_at: string;
}

/**
 * The compact shape GET /bitzas/ (list/browse) actually returns
 * (`BitzaListRead`) — distinct from `Bitza` (`BitzaRead`, the full
 * detail shape from GET /bitzas/{id}). The backend deliberately sends
 * less data for list views; `BitzaService.list()` used to be typed as
 * returning `Bitza[]`, which claimed fields (description, vendor, tags,
 * etc.) that were never actually present in that response.
 */
export interface BitzaListItem {
  id: string;
  name: string;
  kind: BitzaKind;
  parent_id: string | null;
  parent_name: string | null;
  responsible_team_name: string;
  category_name: string | null;
  status: BitzaStatus;
  quantity: number | null;
  fuzzy_state: FuzzyState | null;
  is_checked_out: boolean;
  child_count: number;
  is_root: boolean;
}

export interface BitzaCreate {
  name: string;
  kind: BitzaKind;
  /**
   * Required — the backend rejects a missing/null parent_id outright.
   * There is exactly one root bitza system-wide, created once via the
   * backend CLI's create-root command, never through this endpoint.
   */
  parent_id: string;
  responsible_team_id: string;
  category_id?: string | null;
  description?: string | null;
  tags?: string[];
  stock_mode?: StockMode;
  /** Required by the backend when stock_mode = 'exact'; forbidden otherwise. */
  quantity?: number;
  /** Only meaningful when stock_mode = 'exact'; forbidden when 'fuzzy'. */
  low_stock_threshold?: number;
  fuzzy_state?: FuzzyState;
  purchased_by_user_id?: string;
  vendor?: string;
  purchase_date?: string;
  order_url?: string;
}

export interface BitzaUpdate {
  name?: string;
  parent_id?: string | null;
  responsible_team_id?: string;
  category_id?: string | null;
  description?: string | null;
  tags?: string[];
  low_stock_threshold?: number;
  fuzzy_state?: FuzzyState;
  vendor?: string;
  purchase_date?: string;
  order_url?: string;
}

export interface BitzaRetireRequest {
  reason: RetiredReason;
  note?: string;
}

export interface BitzaReassignTeamRequest {
  team_id: string;
  cascade_scope: CascadeScope;
}

/**
 * POST /bitzas/{id}/reassign-team's actual response — previously
 * discarded entirely (the service typed this call as returning void).
 * updated_count matters most for all_descendants: it's the only
 * confirmation of how many rows the cascade actually touched.
 */
export interface ReassignTeamResponse {
  bitza_id: string;
  team_id: string;
  cascade_scope: CascadeScope;
  updated_count: number;
}

/** Query params for GET /bitzas/ — see "Listing and filtering". */
export interface BitzaListParams {
  parent_id?: string;
  root_only?: boolean;
  kind?: BitzaKind;
  status?: BitzaStatus;
  responsible_team_id?: string;
  category_id?: string;
  retired_reason?: RetiredReason;
}

export interface BitzaImage {
  id: string;
  bitza_id: string;
  is_primary: boolean;
  filename: string;
  created_at: string;
}
