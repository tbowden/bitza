import { HttpClient } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User, UserUpdate } from '../models';

/**
 * Covers /users/me (open to any authenticated user) and the /users/
 * directory. The directory is documented as admin/superuser-gated for
 * account management, but the Team/Bitza trust model assumes any user can
 * add any other user to any team — which needs some way to look someone
 * up. This service calls GET /users/ as the natural read for that picker;
 * if that turns out to 403 for plain users in practice, that's a backend/
 * doc reconciliation, not a frontend change — see the Teams milestone notes.
 */
@Service()
export class UserService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/users`;

  getMe(): Observable<User> {
    return this.http.get<User>(`${this.baseUrl}/me`);
  }

  updateMe(update: UserUpdate): Observable<User> {
    return this.http.patch<User>(`${this.baseUrl}/me`, update);
  }

  list(): Observable<User[]> {
    return this.http.get<User[]>(`${this.baseUrl}/`);
  }

  get(id: string): Observable<User> {
    return this.http.get<User>(`${this.baseUrl}/${id}`);
  }
}
