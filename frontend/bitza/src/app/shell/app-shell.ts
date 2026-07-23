import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { toSignal } from '@angular/core/rxjs-interop';
import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet, Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatMenuModule } from '@angular/material/menu';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { map } from 'rxjs';
import { AppConfigService } from '../core/services/app-config.service';
import { AuthService } from '../core/services/auth.service';

@Component({
  selector: 'app-shell',
  imports: [
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    MatButtonModule,
    MatDividerModule,
    MatIconModule,
    MatListModule,
    MatMenuModule,
    MatSidenavModule,
    MatToolbarModule,
  ],
  template: `
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <mat-sidenav-container class="shell-container">
      <mat-sidenav
        #sidenav
        [mode]="isHandset() ? 'over' : 'side'"
        [opened]="!isHandset()"
        class="shell-sidenav"
      >
        <mat-nav-list>
          <a
            mat-list-item
            routerLink="/bitzas"
            routerLinkActive="active-link"
            (click)="isHandset() && sidenav.close()"
          >
            <mat-icon matListItemIcon>inventory_2</mat-icon>
            <span matListItemTitle>Bitzas</span>
          </a>
          <a
            mat-list-item
            routerLink="/teams"
            routerLinkActive="active-link"
            (click)="isHandset() && sidenav.close()"
          >
            <mat-icon matListItemIcon>groups</mat-icon>
            <span matListItemTitle>{{ config.teamLabelPlural() }}</span>
          </a>

          @if (authService.isAdmin()) {
            <mat-divider></mat-divider>
            <a
              mat-list-item
              routerLink="/users"
              routerLinkActive="active-link"
              (click)="isHandset() && sidenav.close()"
            >
              <mat-icon matListItemIcon>manage_accounts</mat-icon>
              <span matListItemTitle>Users</span>
            </a>
            <a
              mat-list-item
              routerLink="/audit"
              routerLinkActive="active-link"
              (click)="isHandset() && sidenav.close()"
            >
              <mat-icon matListItemIcon>fact_check</mat-icon>
              <span matListItemTitle>Audit log</span>
            </a>
          }
        </mat-nav-list>
      </mat-sidenav>

      <mat-sidenav-content>
        <mat-toolbar color="primary" class="shell-toolbar">
          @if (isHandset()) {
            <button
              mat-icon-button
              type="button"
              aria-label="Toggle navigation menu"
              (click)="sidenav.toggle()"
            >
              <mat-icon>menu</mat-icon>
            </button>
          }

          <span class="shell-title">Bitza</span>
          <span class="shell-spacer"></span>

          @if (authService.currentUser(); as user) {
            <button
              mat-button
              type="button"
              [matMenuTriggerFor]="userMenu"
              [attr.aria-label]="'Account menu for ' + user.username"
            >
              <mat-icon>account_circle</mat-icon>
              {{ user.username }}
            </button>
            <mat-menu #userMenu="matMenu">
              <button mat-menu-item type="button" (click)="onLogout()">
                <mat-icon>logout</mat-icon>
                <span>Sign out</span>
              </button>
            </mat-menu>
          }
        </mat-toolbar>

        <main id="main-content" class="shell-content" tabindex="-1">
          <router-outlet></router-outlet>
        </main>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: `
    .skip-link {
      position: absolute;
      left: -9999px;
      top: 0;
      z-index: 100;
      background: var(--mat-sys-primary);
      color: var(--mat-sys-on-primary);
      padding: 0.75rem 1rem;
      border-radius: 0 0 4px 0;
    }

    .skip-link:focus {
      left: 0;
    }

    .shell-container {
      height: 100vh;
    }

    .shell-sidenav {
      width: var(--bitza-nav-width);
    }

    .shell-toolbar {
      position: sticky;
      top: 0;
      z-index: 10;
    }

    .shell-title {
      font-weight: 600;
      margin-left: 0.5rem;
    }

    .shell-spacer {
      flex: 1 1 auto;
    }

    .shell-content {
      padding: 1.5rem;
      max-width: 1100px;
      margin: 0 auto;
    }

    .active-link {
      background: var(--mat-sys-secondary-container);
    }
  `,
})
export class AppShell {
  protected readonly authService = inject(AuthService);
  protected readonly config = inject(AppConfigService);
  private readonly router = inject(Router);
  private readonly breakpointObserver = inject(BreakpointObserver);

  private readonly isHandsetSignal = toSignal(
    this.breakpointObserver.observe(Breakpoints.Handset).pipe(map((result) => result.matches)),
    { initialValue: false },
  );

  protected readonly isHandset = computed(() => this.isHandsetSignal());

  protected async onLogout(): Promise<void> {
    this.authService.logout().subscribe(() => {
      this.router.navigateByUrl('/login');
    });
  }
}
