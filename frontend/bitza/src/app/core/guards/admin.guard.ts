import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * UI-only gate for admin/superuser sections (user management, audit log).
 * The backend enforces the real permission — see "User roles" in
 * bitza_project_context.md — this guard exists purely so the wrong nav
 * items and pages never render for a plain user.
 */
export const adminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAdmin()) {
    return true;
  }

  return router.createUrlTree(['/']);
};
