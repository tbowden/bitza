import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, catchError, filter, switchMap, take, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { TokenStorageService } from '../services/token-storage.service';

const AUTH_FREE_PATHS = ['/auth/login', '/auth/refresh'];

// Module-level (singleton) refresh coordination state, shared across every
// request that flows through this interceptor, so concurrent 401s trigger
// exactly one refresh call instead of a stampede.
let isRefreshing = false;
const refreshedAccessToken$ = new BehaviorSubject<string | null>(null);

/**
 * Transparent 401 -> refresh -> retry, per the interceptor-based strategy
 * documented as "strongly recommended" in bitza_project_context.md.
 * Redirects to /login only if the refresh call itself fails.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const tokenStorage = inject(TokenStorageService);
  const authService = inject(AuthService);
  const router = inject(Router);

  const isAuthFree = AUTH_FREE_PATHS.some((path) => req.url.includes(path));
  const accessToken = tokenStorage.getAccessToken();

  const authedReq = accessToken && !isAuthFree ? withBearer(req, accessToken) : req;

  return next(authedReq).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && !isAuthFree) {
        return handleUnauthorized(authedReq, next, authService, router);
      }
      return throwError(() => error);
    }),
  );
};

function withBearer(req: HttpRequest<unknown>, accessToken: string): HttpRequest<unknown> {
  return req.clone({ setHeaders: { Authorization: `Bearer ${accessToken}` } });
}

function handleUnauthorized(
  req: HttpRequest<unknown>,
  next: HttpHandlerFn,
  authService: AuthService,
  router: Router,
): Observable<HttpEvent<unknown>> {
  if (!isRefreshing) {
    isRefreshing = true;
    refreshedAccessToken$.next(null);

    return authService.refreshTokens().pipe(
      switchMap((tokens) => {
        isRefreshing = false;
        refreshedAccessToken$.next(tokens.access_token);
        return next(withBearer(req, tokens.access_token));
      }),
      catchError((refreshError: unknown) => {
        isRefreshing = false;
        authService.clearSession();
        router.navigate(['/login']);
        return throwError(() => refreshError);
      }),
    );
  }

  // A refresh triggered by another in-flight request is already underway —
  // wait for it to finish, then retry with the resulting token.
  return refreshedAccessToken$.pipe(
    filter((token): token is string => token !== null),
    take(1),
    switchMap((token) => next(withBearer(req, token))),
  );
}
