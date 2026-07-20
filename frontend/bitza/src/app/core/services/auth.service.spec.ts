import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';
import { TokenStorageService } from './token-storage.service';

describe('AuthService', () => {
  let authService: AuthService;
  let tokenStorage: TokenStorageService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    authService = TestBed.inject(AuthService);
    tokenStorage = TestBed.inject(TokenStorageService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('stores tokens and loads the current user on login', async () => {
    const loginPromise = firstValueFrom(authService.login('sam', 'hunter2'));

    const loginReq = httpMock.expectOne(`${environment.apiUrl}/auth/login`);
    expect(loginReq.request.body).toEqual({ identifier: 'sam', password: 'hunter2' });
    loginReq.flush({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
    });

    const meReq = httpMock.expectOne(`${environment.apiUrl}/users/me`);
    meReq.flush({
      id: 'u1',
      email: 'sam@example.com',
      username: 'sam',
      role: 'user',
      is_suspended: false,
      created_at: '2026-01-01T00:00:00Z',
    });

    const user = await loginPromise;

    expect(user.username).toBe('sam');
    expect(tokenStorage.getAccessToken()).toBe('access-1');
    expect(tokenStorage.getRefreshToken()).toBe('refresh-1');
    expect(authService.isAuthenticated()).toBe(true);
    expect(authService.currentUser()?.username).toBe('sam');
  });

  it('rotates the refresh token on refresh, never reusing the old one', async () => {
    tokenStorage.setTokens({
      access_token: 'expired-access',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
    });

    const refreshPromise = firstValueFrom(authService.refreshTokens());

    const req = httpMock.expectOne(`${environment.apiUrl}/auth/refresh`);
    expect(req.request.body).toEqual({ refresh_token: 'refresh-1' });
    req.flush({
      access_token: 'access-2',
      refresh_token: 'refresh-2',
      token_type: 'bearer',
    });

    await refreshPromise;

    expect(tokenStorage.getAccessToken()).toBe('access-2');
    expect(tokenStorage.getRefreshToken()).toBe('refresh-2');
  });

  it('clears local session on logout regardless of server response', async () => {
    tokenStorage.setTokens({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
    });

    const logoutPromise = firstValueFrom(authService.logout());

    const req = httpMock.expectOne(`${environment.apiUrl}/auth/logout`);
    req.flush(null, { status: 500, statusText: 'Server Error' });

    await logoutPromise;

    expect(tokenStorage.getAccessToken()).toBeNull();
    expect(tokenStorage.getRefreshToken()).toBeNull();
    expect(authService.isAuthenticated()).toBe(false);
    expect(authService.currentUser()).toBeNull();
  });
});
