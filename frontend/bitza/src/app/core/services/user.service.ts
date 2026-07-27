import { HttpClient } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AdminUserUpdate, User, UserCreate, UserDirectoryEntry, UserUpdate } from '../models';

/**
 * Covers /users/me (open to any authenticated user), the admin/superuser-
 * only /users/ directory (`list`, `create`, `adminUpdate`, `delete`), and
 * /users/directory (`directory`) — a minimal, ungated listing added
 * specifically so pickers like the team add-member dialog can look
 * someone up without needing admin/superuser access.
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

  /** Admin/superuser only — see UserService.list_users's permission matrix. */
  list(): Observable<User[]> {
    return this.http.get<User[]>(`${this.baseUrl}/`);
  }

  /** Any authenticated user — id + display_name only. For pickers, not account management. */
  directory(): Observable<UserDirectoryEntry[]> {
    return this.http.get<UserDirectoryEntry[]>(`${this.baseUrl}/directory`);
  }

  get(id: string): Observable<User> {
    return this.http.get<User>(`${this.baseUrl}/${id}`);
  }

  /** Admin/superuser only — see UserCreate's doc comment for the shape caveat. */
  create(user: UserCreate): Observable<User> {
    return this.http.post<User>(`${this.baseUrl}/`, user);
  }

  /** Admin/superuser only. The backend is the source of truth on who may edit whom. */
  adminUpdate(id: string, update: AdminUserUpdate): Observable<User> {
    return this.http.patch<User>(`${this.baseUrl}/${id}`, update);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
