export interface Category {
  id: string;
  name: string;
  created_by: string | null;
  /** Populated by the service. */
  bitza_count: number;
  created_at: string;
}

export interface CategoryCreate {
  name: string;
}

export interface CategoryUpdate {
  name: string;
}
