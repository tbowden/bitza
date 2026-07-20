import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { MAT_ICON_DEFAULT_OPTIONS } from '@angular/material/icon';
import { catchError, of } from 'rxjs';

import { routes } from './app.routes';
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { AuthService } from './core/services/auth.service';
import { TokenStorageService } from './core/services/token-storage.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    { provide: MAT_ICON_DEFAULT_OPTIONS, useValue: { fontSet: 'material-symbols-outlined' } },
    // On a hard reload with tokens already in localStorage, restore the
    // current-user profile before the app renders so guards and the shell
    // see an accurate isAuthenticated/currentUser state immediately.
    provideAppInitializer(() => {
      const tokenStorage = inject(TokenStorageService);
      const authService = inject(AuthService);
      if (!tokenStorage.hasTokens()) {
        return of(null);
      }
      return authService.loadCurrentUser().pipe(
        catchError(() => {
          authService.clearSession();
          return of(null);
        }),
      );
    }),
  ],
};
