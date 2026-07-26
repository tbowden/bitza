import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { BitzaService } from '../services/bitza.service';

/**
 * There is exactly one root bitza system-wide (see the backend's
 * SystemConfig model) — `/bitzas` with no id no longer means "browse
 * root-level items", it means "go to the one root". Redirects there
 * transparently. If the system hasn't been bootstrapped yet (the
 * backend CLI's create-root hasn't run), falls through and lets
 * BitzaBrowser render its own "not set up yet" state instead of
 * crashing — this is a real, expected state right after a fresh
 * deployment, not an error.
 */
export const redirectToRootGuard: CanActivateFn = () => {
  const bitzaService = inject(BitzaService);
  const router = inject(Router);

  return bitzaService.list({ root_only: true }).pipe(
    map((roots) => (roots.length > 0 ? router.createUrlTree(['/bitzas', roots[0].id]) : true)),
    catchError(() => of(true)),
  );
};
