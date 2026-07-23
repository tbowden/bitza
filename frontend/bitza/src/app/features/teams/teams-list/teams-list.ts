import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { catchError, of, switchMap } from 'rxjs';
import { AppConfigService } from '../../../core/services/app-config.service';
import { AuthService } from '../../../core/services/auth.service';
import { TeamService } from '../../../core/services/team.service';
import { Team } from '../../../core/models';
import { TeamFormDialog, TeamFormResult } from '../team-form-dialog/team-form-dialog';

@Component({
  selector: 'app-teams-list',
  imports: [
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
  ],
  template: `
    <div class="page-header">
      <h1>{{ config.teamLabelPlural() }}</h1>
      <button mat-flat-button color="primary" type="button" (click)="onCreate()">
        <mat-icon>add</mat-icon>
        New {{ config.teamLabelSingular().toLowerCase() }}
      </button>
    </div>

    <mat-slide-toggle [checked]="onlyMine()" (change)="onlyMine.set($event.checked)">
      Only {{ config.teamLabelPlural().toLowerCase() }} I'm on
    </mat-slide-toggle>

    @if (loadError()) {
      <p class="error-text" role="alert">
        Couldn't load {{ config.teamLabelPlural().toLowerCase() }}. Try refreshing.
      </p>
    } @else if (teamsLoading()) {
      <div class="loading-row">
        <mat-progress-spinner diameter="28" mode="indeterminate"></mat-progress-spinner>
      </div>
    } @else if (visibleTeams().length === 0) {
      <p>No {{ config.teamLabelPlural().toLowerCase() }} to show yet.</p>
    } @else {
      <div class="team-grid">
        @for (team of visibleTeams(); track team.id) {
          <mat-card
            class="team-card"
            role="button"
            tabindex="0"
            [attr.aria-label]="'Open ' + team.name"
            (click)="openTeam(team.id)"
            (keydown.enter)="openTeam(team.id)"
            (keydown.space)="openTeam(team.id); $event.preventDefault()"
          >
            <mat-card-header>
              <mat-card-title
                ><h2>{{ team.name }}</h2></mat-card-title
              >
            </mat-card-header>
            @if (team.description) {
              <mat-card-content>{{ team.description }}</mat-card-content>
            }
          </mat-card>
        }
      </div>
    }
  `,
  styles: `
    mat-card-title h2 {
      margin: 0;
      font: inherit;
    }

    .page-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1rem;
    }

    .team-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }

    .team-card {
      cursor: pointer;
    }

    .loading-row {
      display: flex;
      justify-content: center;
      padding: 2rem 0;
    }

    .error-text {
      color: var(--mat-sys-error);
    }
  `,
})
export class TeamsList {
  protected readonly config = inject(AppConfigService);
  private readonly authService = inject(AuthService);
  private readonly teamService = inject(TeamService);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);

  protected readonly onlyMine = signal(false);

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);

  private readonly allTeams = toSignal(
    this.reload$.pipe(
      switchMap(() =>
        this.teamService.list().pipe(
          catchError(() => {
            this.loadErrorSignal.set(true);
            return of<Team[]>([]);
          }),
        ),
      ),
    ),
    { initialValue: undefined },
  );

  private readonly myTeams = toSignal(
    this.reload$.pipe(
      switchMap(() => {
        const userId = this.authService.currentUser()?.id;
        if (!userId) {
          return of<Team[]>([]);
        }
        return this.teamService.list(userId).pipe(catchError(() => of<Team[]>([])));
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly teamsLoading = computed(() =>
    this.onlyMine() ? this.myTeams() === undefined : this.allTeams() === undefined,
  );

  protected readonly visibleTeams = computed(() => {
    const teams = this.onlyMine() ? this.myTeams() : this.allTeams();
    return teams ?? [];
  });

  protected onCreate(): void {
    const dialogRef = this.dialog.open(TeamFormDialog, { width: '480px' });
    dialogRef.afterClosed().subscribe((result?: TeamFormResult) => {
      if (!result) {
        return;
      }
      this.teamService.create(result).subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected openTeam(teamId: string): void {
    this.router.navigate(['/teams', teamId]);
  }
}
