import { HttpClient } from '@angular/common/http';
import { Service, computed, inject, signal } from '@angular/core';
import { Observable, catchError, of, switchMap, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthTokens, LoginRequest, User } from '../models';
import { TokenStorageService } from './token-storage.service';

@Service()
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly tokenStorage = inject(TokenStorageService);

  private readonly baseUrl = `${environment.apiUrl}/auth`;

  private readonly currentUserSignal = signal<User | null>(null);
  private readonly authenticatedSignal = signal<boolean>(this.tokenStorage.hasTokens());

  readonly currentUser = this.currentUserSignal.asReadonly();
  readonly isAuthenticated = this.authenticatedSignal.asReadonly();
  readonly isAdmin = computed(() => {
    const role = this.currentUserSignal()?.role;
    return role === 'admin' || role === 'superuser';
  });
  readonly isSuperuser = computed(() => this.currentUserSignal()?.role === 'superuser');

  /** Logs in, stores tokens, then loads the current user profile. */
  login(identifier: string, password: string): Observable<User> {
    const body: LoginRequest = { identifier, password };
    return this.http.post<AuthTokens>(`${this.baseUrl}/login`, body).pipe(
      tap((tokens) => this.storeSession(tokens)),
      switchMap(() => this.loadCurrentUser()),
    );
  }

  /** Fetches /users/me and populates the current-user signal. */
  loadCurrentUser(): Observable<User> {
    return this.http
      .get<User>(`${environment.apiUrl}/users/me`)
      .pipe(tap((user) => this.currentUserSignal.set(user)));
  }

  /**
   * Called by the auth interceptor on a 401. Rotational refresh — always
   * store the *new* refresh token from the response, never reuse the old
   * one (see "Token expiry and refresh").
   */
  refreshTokens(): Observable<AuthTokens> {
    const refreshToken = this.tokenStorage.getRefreshToken();
    if (!refreshToken) {
      this.clearSession();
      return throwError(() => new Error('No refresh token available'));
    }
    return this.http
      .post<AuthTokens>(`${this.baseUrl}/refresh`, { refresh_token: refreshToken })
      .pipe(tap((tokens) => this.storeSession(tokens)));
  }

  /**
   * Calls the logout endpoint, then clears local session state regardless
   * of the response — the access token is short-lived anyway.
   */
  logout(): Observable<void> {
    const refreshToken = this.tokenStorage.getRefreshToken();
    const request = refreshToken
      ? this.http.post<void>(`${this.baseUrl}/logout`, { refresh_token: refreshToken })
      : of(undefined);

    return request.pipe(
      catchError(() => of(undefined)),
      tap(() => this.clearSession()),
    );
  }

  clearSession(): void {
    this.tokenStorage.clear();
    this.currentUserSignal.set(null);
    this.authenticatedSignal.set(false);
  }

  private storeSession(tokens: AuthTokens): void {
    this.tokenStorage.setTokens(tokens);
    this.authenticatedSignal.set(true);
  }
}
