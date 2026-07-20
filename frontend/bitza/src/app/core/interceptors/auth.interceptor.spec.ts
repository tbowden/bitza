import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { authInterceptor } from './auth.interceptor';
import { TokenStorageService } from '../services/token-storage.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let tokenStorage: TokenStorageService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        provideRouter([{ path: 'login', children: [] }]),
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    tokenStorage = TestBed.inject(TokenStorageService);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('attaches the bearer token to outgoing requests', () => {
    tokenStorage.setTokens({
      access_token: 'access-1',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
    });

    http.get(`${environment.apiUrl}/bitzas/`).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/`);
    expect(req.request.headers.get('Authorization')).toBe('Bearer access-1');
    req.flush([]);
  });

  it('refreshes once on a 401 and retries the original request', async () => {
    tokenStorage.setTokens({
      access_token: 'stale-access',
      refresh_token: 'refresh-1',
      token_type: 'bearer',
    });

    const resultPromise = firstValueFrom(http.get(`${environment.apiUrl}/bitzas/`));

    const firstAttempt = httpMock.expectOne(`${environment.apiUrl}/bitzas/`);
    expect(firstAttempt.request.headers.get('Authorization')).toBe('Bearer stale-access');
    firstAttempt.flush(null, { status: 401, statusText: 'Unauthorized' });

    const refreshReq = httpMock.expectOne(`${environment.apiUrl}/auth/refresh`);
    expect(refreshReq.request.body).toEqual({ refresh_token: 'refresh-1' });
    refreshReq.flush({
      access_token: 'fresh-access',
      refresh_token: 'fresh-refresh',
      token_type: 'bearer',
    });

    const retryReq = httpMock.expectOne(`${environment.apiUrl}/bitzas/`);
    expect(retryReq.request.headers.get('Authorization')).toBe('Bearer fresh-access');
    retryReq.flush([{ id: 'b1' }]);

    const result = await resultPromise;
    expect(result).toEqual([{ id: 'b1' }]);
    expect(tokenStorage.getAccessToken()).toBe('fresh-access');
    expect(tokenStorage.getRefreshToken()).toBe('fresh-refresh');
  });

  it('clears the session when the refresh call itself fails', async () => {
    tokenStorage.setTokens({
      access_token: 'stale-access',
      refresh_token: 'dead-refresh',
      token_type: 'bearer',
    });

    const resultPromise = firstValueFrom(http.get(`${environment.apiUrl}/bitzas/`)).catch(
      (err) => err,
    );

    const firstAttempt = httpMock.expectOne(`${environment.apiUrl}/bitzas/`);
    firstAttempt.flush(null, { status: 401, statusText: 'Unauthorized' });

    const refreshReq = httpMock.expectOne(`${environment.apiUrl}/auth/refresh`);
    refreshReq.flush(null, { status: 401, statusText: 'Unauthorized' });

    await resultPromise;

    expect(tokenStorage.getAccessToken()).toBeNull();
    expect(tokenStorage.getRefreshToken()).toBeNull();
  });
});
