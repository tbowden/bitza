/**
 * "Currently checked out" is always derived from the newest row with
 * `checked_in_at === null` — never a separate state field on the Bitza
 * itself. See "Checkout (kind = mobile)".
 */
export interface Checkout {
  id: string;
  bitza_id: string;
  user_id: string;
  /** Free-text snapshot, not a live FK — safe even if the team is deleted later. */
  team_context: string | null;
  note: string | null;
  checked_out_at: string;
  checked_in_at: string | null;
}

export interface CheckoutRequest {
  team_context?: string;
  note?: string;
}

export interface CheckinRequest {
  note?: string;
}
