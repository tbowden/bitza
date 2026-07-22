import { HttpClient } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CheckinRequest, Checkout, CheckoutRequest } from '../models';

@Service()
export class CheckoutService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/bitzas`;

  /**
   * The holder is always the current authenticated user — there's no
   * checking something out on someone else's behalf. If team_context is
   * omitted, the backend pre-fills it from the holder's primary team at
   * the moment of checkout; the frontend doesn't need to compute that
   * itself. See "Checkout (kind = mobile)".
   */
  checkout(bitzaId: string, request: CheckoutRequest): Observable<Checkout> {
    return this.http.post<Checkout>(`${this.baseUrl}/${bitzaId}/checkout`, request);
  }

  /** Anyone may check something in, not just whoever checked it out. */
  checkin(bitzaId: string, request: CheckinRequest): Observable<Checkout> {
    return this.http.post<Checkout>(`${this.baseUrl}/${bitzaId}/checkin`, request);
  }

  /** Newest first. "Currently checked out" is derived: the row (if any) with checked_in_at === null. */
  history(bitzaId: string): Observable<Checkout[]> {
    return this.http.get<Checkout[]>(`${this.baseUrl}/${bitzaId}/checkouts`);
  }
}
