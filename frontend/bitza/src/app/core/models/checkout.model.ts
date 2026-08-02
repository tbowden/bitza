import { BitzaKind } from './bitza.model';

/**
 * "Currently checked out" is always derived from the newest row with
 * `checked_in_at === null` — never a separate state field on the Bitza
 * itself. See "Checkout (kind = mobile)".
 */
export interface Checkout {
  id: string;
  bitza_id: string;
  holder_id: string | null;
  holder_display_name: string;
  /** Free-text snapshot, not a live FK — safe even if the project is deleted later. */
  project_context: string | null;
  note: string | null;
  checked_out_at: string;
  checked_in_at: string | null;
}

/**
 * One row of GET /checkouts/mine — every bitza currently checked out to
 * the current user, across the whole tree. Distinct from `Checkout`
 * (scoped to one bitza's history, holder info populated): this is
 * scoped to a holder (implicitly "you") across every bitza, so it
 * carries the bitza's own name/kind instead.
 */
export interface MyCheckout {
  id: string;
  bitza_id: string;
  bitza_name: string;
  /** Null only in the edge case where the bitza row itself is gone. */
  bitza_kind: BitzaKind | null;
  project_context: string | null;
  checked_out_at: string;
  note: string | null;
}

export interface CheckoutRequest {
  project_context?: string;
  note?: string;
}

export interface CheckinRequest {
  note?: string;
}
