import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';
import { redirectToRootGuard } from './core/guards/redirect-to-root.guard';

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
      { path: '', redirectTo: 'me', pathMatch: 'full' },
      {
        path: 'bitzas',
        canActivate: [redirectToRootGuard],
        loadComponent: () =>
          import('./features/bitzas/bitza-browser/bitza-browser').then((m) => m.BitzaBrowser),
        title: 'Bitzas',
      },
      {
        path: 'bitzas/:id',
        loadComponent: () =>
          import('./features/bitzas/bitza-browser/bitza-browser').then((m) => m.BitzaBrowser),
        title: 'Bitza',
      },
      {
        // Canonical URL baked into printed QR/NFC tags is singular
        // ("/bitza/<id>/", per bitza_project_context.md's "Scanning"
        // section) and must keep working even if the in-app browsing
        // route is ever renamed — hence a plain redirect rather than
        // pointing both paths at the same component.
        path: 'bitza/:id',
        redirectTo: 'bitzas/:id',
      },
      {
        path: 'teams',
        loadComponent: () =>
          import('./features/teams/teams-list/teams-list').then((m) => m.TeamsList),
        title: 'Teams',
      },
      {
        path: 'teams/:id',
        loadComponent: () =>
          import('./features/teams/team-detail/team-detail').then((m) => m.TeamDetail),
        title: 'Team detail',
      },
      {
        path: 'me',
        loadComponent: () => import('./features/me/me-page/me-page').then((m) => m.MePage),
        title: 'Me',
      },
      {
        path: 'users',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./features/users/users-list/users-list').then((m) => m.UsersList),
        title: 'Users',
      },
      {
        path: 'audit',
        canActivate: [adminGuard],
        loadComponent: () => import('./features/audit/audit-log/audit-log').then((m) => m.AuditLog),
        title: 'Audit log',
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
