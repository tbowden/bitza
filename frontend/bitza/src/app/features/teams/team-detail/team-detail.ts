import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { catchError, of, switchMap } from 'rxjs';
import { AppConfigService } from '../../../core/services/app-config.service';
import { TeamService } from '../../../core/services/team.service';
import { Team, TeamMember } from '../../../core/models';
import { ConfirmDialog, ConfirmDialogData } from '../../../shared/confirm-dialog/confirm-dialog';
import {
  AddMemberDialog,
  AddMemberDialogData,
  AddMemberResult,
} from '../add-member-dialog/add-member-dialog';
import { TeamFormDialog, TeamFormResult } from '../team-form-dialog/team-form-dialog';

@Component({
  selector: 'app-team-detail',
  imports: [
    RouterLink,
    MatButtonModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatTooltipModule,
  ],
  template: `
    <a routerLink="/teams" class="back-link">
      <mat-icon>arrow_back</mat-icon>
      Back to {{ config.teamLabelPlural().toLowerCase() }}
    </a>

    @if (loadError()) {
      <p class="error-text" role="alert">
        Couldn't load this {{ config.teamLabelSingular().toLowerCase() }}.
      </p>
    } @else if (team(); as team) {
      <div class="page-header">
        <div>
          <h1>{{ team.name }}</h1>
          @if (team.description) {
            <p class="description">{{ team.description }}</p>
          }
        </div>
        <div class="header-actions">
          <button mat-stroked-button type="button" (click)="onEditTeam(team)">
            <mat-icon>edit</mat-icon>
            Edit
          </button>
          <button mat-stroked-button color="warn" type="button" (click)="onDeleteTeam(team)">
            <mat-icon>delete</mat-icon>
            Delete
          </button>
        </div>
      </div>

      <div class="members-header">
        <h2>Members</h2>
        <button mat-flat-button color="primary" type="button" (click)="onAddMember(team.id)">
          <mat-icon>person_add</mat-icon>
          Add member
        </button>
      </div>

      @if (membersLoading()) {
        <div class="loading-row">
          <mat-progress-spinner diameter="28" mode="indeterminate"></mat-progress-spinner>
        </div>
      } @else if (members().length === 0) {
        <p>No members yet.</p>
      } @else {
        <table mat-table [dataSource]="members()" class="members-table">
          <ng-container matColumnDef="username">
            <th mat-header-cell *matHeaderCellDef>Member</th>
            <td mat-cell *matCellDef="let member">
              {{ member.username ?? member.user_id }}
              @if (member.email) {
                <span class="member-email">{{ member.email }}</span>
              }
            </td>
          </ng-container>

          <ng-container matColumnDef="primary">
            <th mat-header-cell *matHeaderCellDef>Primary</th>
            <td mat-cell *matCellDef="let member">
              <button
                mat-icon-button
                type="button"
                [attr.aria-pressed]="member.is_primary"
                [attr.aria-label]="
                  member.is_primary
                    ? 'Unset ' + (member.username ?? 'this member') + ' as primary team'
                    : 'Set ' + (member.username ?? 'this member') + ' as primary team'
                "
                [matTooltip]="
                  member.is_primary ? 'Primary team — click to unset' : 'Set as primary team'
                "
                (click)="onTogglePrimary(team.id, member)"
              >
                <mat-icon>{{ member.is_primary ? 'star' : 'star_border' }}</mat-icon>
              </button>
            </td>
          </ng-container>

          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let member">
              <button
                mat-icon-button
                type="button"
                aria-label="Remove member"
                matTooltip="Remove from team"
                (click)="onRemoveMember(team.id, member)"
              >
                <mat-icon>person_remove</mat-icon>
              </button>
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
        </table>
      }
    }
  `,
  styles: `
    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      margin-bottom: 1rem;
      text-decoration: none;
      color: var(--mat-sys-primary);
    }

    .page-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.5rem;
    }

    .description {
      color: var(--mat-sys-on-surface-variant);
    }

    .header-actions {
      display: flex;
      gap: 0.5rem;
      flex-shrink: 0;
    }

    .members-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.75rem;
    }

    .members-table {
      width: 100%;
    }

    .member-email {
      display: block;
      font-size: 0.8125rem;
      color: var(--mat-sys-on-surface-variant);
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
export class TeamDetail {
  protected readonly config = inject(AppConfigService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly teamService = inject(TeamService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly columns = ['username', 'primary', 'actions'];

  private readonly teamId = toSignal(
    this.route.paramMap.pipe(switchMap((params) => of(params.get('id') ?? ''))),
    { initialValue: '' },
  );

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);
  private readonly teamId$ = toObservable(this.teamId);

  protected readonly team = toSignal(
    this.teamId$.pipe(
      switchMap((id) => {
        if (!id) {
          return of(undefined);
        }
        return this.teamService.get(id).pipe(
          catchError(() => {
            this.loadErrorSignal.set(true);
            return of(undefined);
          }),
        );
      }),
    ),
    { initialValue: undefined },
  );

  private readonly membersResult = toSignal(
    this.reload$.pipe(
      switchMap(() => {
        const id = this.teamId();
        if (!id) {
          return of<TeamMember[] | undefined>(undefined);
        }
        return this.teamService.listMembers(id).pipe(catchError(() => of<TeamMember[]>([])));
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly membersLoading = computed(() => this.membersResult() === undefined);
  protected readonly members = computed(() => this.membersResult() ?? []);

  protected onEditTeam(team: Team): void {
    const dialogRef = this.dialog.open(TeamFormDialog, {
      width: '480px',
      data: { team },
    });
    dialogRef.afterClosed().subscribe((result?: TeamFormResult) => {
      if (!result) {
        return;
      }
      this.teamService.update(team.id, result).subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onDeleteTeam(team: Team): void {
    const data: ConfirmDialogData = {
      title: `Delete ${team.name}?`,
      message: `This can't be undone. It will fail if any bitza is still responsible-to this ${this.config
        .teamLabelSingular()
        .toLowerCase()}.`,
      confirmLabel: 'Delete',
      destructive: true,
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.teamService.delete(team.id).subscribe({
        next: () => this.router.navigateByUrl('/teams'),
        error: (err: HttpErrorResponse) => {
          if (err.status === 409) {
            this.snackBar.open(
              `Can't delete — one or more bitzas are still responsible to this ${this.config
                .teamLabelSingular()
                .toLowerCase()}.`,
              'Dismiss',
              { duration: 6000 },
            );
          } else {
            this.snackBar.open('Something went wrong deleting this team.', 'Dismiss', {
              duration: 6000,
            });
          }
        },
      });
    });
  }

  protected onAddMember(teamId: string): void {
    const data: AddMemberDialogData = {
      existingMemberUserIds: this.members().map((member) => member.user_id),
    };
    const dialogRef = this.dialog.open(AddMemberDialog, { width: '480px', data });
    dialogRef.afterClosed().subscribe((result?: AddMemberResult) => {
      if (!result) {
        return;
      }
      this.teamService
        .addMember(teamId, { user_id: result.userId, is_primary: result.isPrimary })
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onTogglePrimary(teamId: string, member: TeamMember): void {
    this.teamService
      .setPrimary(teamId, member.user_id, !member.is_primary)
      .subscribe(() => this.reload.update((n) => n + 1));
  }

  protected onRemoveMember(teamId: string, member: TeamMember): void {
    const data: ConfirmDialogData = {
      title: 'Remove member?',
      message: `Remove ${member.username ?? 'this person'} from the team.`,
      confirmLabel: 'Remove',
      destructive: true,
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.teamService
        .removeMember(teamId, member.user_id)
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }
}
