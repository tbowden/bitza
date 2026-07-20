/**
 * Only exact-mode stock produces a log entry; fuzzy_state is a plain
 * PATCH with no history. See "Stock (kind = stock)".
 */
export interface StockLog {
  id: string;
  bitza_id: string;
  delta: number;
  note: string | null;
  user_id: string;
  created_at: string;
}

export interface StockAdjustmentRequest {
  delta: number;
  note?: string;
}
