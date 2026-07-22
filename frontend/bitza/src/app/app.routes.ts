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
