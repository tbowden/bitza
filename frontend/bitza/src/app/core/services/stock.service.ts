import { HttpClient } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { StockAdjustmentRequest, StockLog } from '../models';

/**
 * Exact-mode stock only — fuzzy_state has no log and is edited via a
 * plain PATCH on the bitza itself (already covered by BitzaService /
 * the bitza edit dialog). See "Stock (kind = stock)".
 */
@Service()
export class StockService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/bitzas`;

  /** Positive = stock in, negative = stock out. Backend rejects with 422 if it would go negative. */
  adjust(bitzaId: string, request: StockAdjustmentRequest): Observable<StockLog> {
    return this.http.post<StockLog>(`${this.baseUrl}/${bitzaId}/stock-adjustments`, request);
  }

  /** Newest first. */
  history(bitzaId: string): Observable<StockLog[]> {
    return this.http.get<StockLog[]>(`${this.baseUrl}/${bitzaId}/stock-adjustments`);
  }
}
