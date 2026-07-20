import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
    title: 'Sign in - Bitza',
  },
  {
    path: '',
    loadComponent: () => import('./shell/app-shell').then((m) => m.AppShell),
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'bitzas', pathMatch: 'full' },
      {
        path: 'bitzas',
        loadComponent: () =>
          import('./features/bitzas/bitzas-placeholder').then((m) => m.BitzasPlaceholder),
        title: 'Bitzas',
      },
      {
        path: 'teams',
        loadComponent: () =>
          import('./features/teams/teams-placeholder').then((m) => m.TeamsPlaceholder),
        title: 'Teams',
      },
      {
        path: 'users',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/users/users-placeholder').then((m) => m.UsersPlaceholder),
        title: 'Users',
      },
      {
        path: 'audit',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/audit/audit-placeholder').then((m) => m.AuditPlaceholder),
        title: 'Audit log',
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
