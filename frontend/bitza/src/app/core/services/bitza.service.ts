import { HttpClient, HttpParams } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Bitza,
  BitzaCreate,
  BitzaListParams,
  BitzaReassignTeamRequest,
  BitzaRetireRequest,
  BitzaUpdate,
} from '../models';

@Service()
export class BitzaService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/bitzas`;

  /**
   * Direct children (or root-level) only — this never recurses, per
   * "Direct-children-only reads" in bitza_project_context.md. Building a
   * "show everything nested here" view means issuing repeated calls from
   * here, not asking the backend to walk the tree.
   */
  list(params: BitzaListParams = {}): Observable<Bitza[]> {
    let httpParams = new HttpParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        httpParams = httpParams.set(key, String(value));
      }
    }
    return this.http.get<Bitza[]>(`${this.baseUrl}/`, { params: httpParams });
  }

  get(id: string): Observable<Bitza> {
    return this.http.get<Bitza>(`${this.baseUrl}/${id}`);
  }

  create(bitza: BitzaCreate): Observable<Bitza> {
    return this.http.post<Bitza>(`${this.baseUrl}/`, bitza);
  }

  update(id: string, bitza: BitzaUpdate): Observable<Bitza> {
    return this.http.patch<Bitza>(`${this.baseUrl}/${id}`, bitza);
  }

  retire(id: string, request: BitzaRetireRequest): Observable<Bitza> {
    return this.http.post<Bitza>(`${this.baseUrl}/${id}/retire`, request);
  }

  reactivate(id: string): Observable<Bitza> {
    return this.http.post<Bitza>(`${this.baseUrl}/${id}/reactivate`, {});
  }

  /**
   * `cascade_scope` is required and never defaulted by the backend — any
   * default shown in a picker is frontend UX only. See
   * "Reassigning responsible team" in bitza_project_context.md.
   */
  reassignTeam(id: string, request: BitzaReassignTeamRequest): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/${id}/reassign-team`, request);
  }

  /** Admin/superuser only; 409 if the bitza still has children. */
  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
