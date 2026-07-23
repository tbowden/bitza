import { HttpClient, HttpParams } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuditListParams, AuditLogEntry } from '../models';

/**
 * Admin/superuser only — the one other permission-gated read in the app
 * besides account management. See "Audit log" in the restoration doc.
 */
@Service()
export class AuditService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/audit`;

  list(params: AuditListParams = {}): Observable<AuditLogEntry[]> {
    let httpParams = new HttpParams();
    for (const [key, value] of Object.entries(params)) {
      if (value) {
        httpParams = httpParams.set(key, value);
      }
    }
    return this.http.get<AuditLogEntry[]>(`${this.baseUrl}/`, { params: httpParams });
  }
}
