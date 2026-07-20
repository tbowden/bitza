import { Service } from '@angular/core';
import { AuthTokens } from '../models';

const ACCESS_TOKEN_KEY = 'bitza_access_token';
const REFRESH_TOKEN_KEY = 'bitza_refresh_token';

/**
 * Both tokens are stored in localStorage per bitza_project_context.md
 * ("Token storage") — they're returned in the response body, not as
 * cookies. If httpOnly cookies are ever needed for XSS hardening, that's
 * a backend change first; this service would then just stop being used.
 */
@Service()
export class TokenStorageService {
  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  setTokens(tokens: AuthTokens): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }

  clear(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }

  hasTokens(): boolean {
    return !!this.getAccessToken();
  }
}
