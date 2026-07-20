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
  responsible_team_id: string;
  status: BitzaStatus;
  retired_reason: RetiredReason | null;
  retired_note: string | null;
  category_id: string | null;
  description?: string | null;

  // stock (kind = 'stock') only
  stock_mode?: StockMode | null;
  quantity?: number | null;
  fuzzy_state?: FuzzyState | null;

  // acquisition / provenance
  purchased_by_user_id?: string | null;
  vendor?: string | null;
  purchase_date?: string | null;
  order_url?: string | null;

  created_at: string;
  updated_at: string;
}

export interface BitzaCreate {
  name: string;
  kind: BitzaKind;
  parent_id?: string | null;
  responsible_team_id: string;
  category_id?: string | null;
  description?: string | null;
  stock_mode?: StockMode;
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
