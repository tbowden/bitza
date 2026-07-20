/**
 * Auth contract — see bitza_project_context.md "Auth contract".
 * `identifier` accepts either an email or a username; there is only ever
 * one field, never separate email/username inputs.
 */
export interface LoginRequest {
  identifier: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface LogoutRequest {
  refresh_token: string;
}

/** Response shape for both /auth/login and /auth/refresh. */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
