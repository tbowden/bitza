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
import { ProjectService } from '../../../core/services/project.service';
import { Project, ProjectMember } from '../../../core/models';
import { ConfirmDialog, ConfirmDialogData } from '../../../shared/confirm-dialog/confirm-dialog';
import {
  AddMemberDialog,
  AddMemberDialogData,
  AddMemberResult,
} from '../add-member-dialog/add-member-dialog';
import { ProjectFormDialog, ProjectFormResult } from '../project-form-dialog/project-form-dialog';

@Component({
  selector: 'app-project-detail',
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
    <a routerLink="/projects" class="back-link">
      <mat-icon>arrow_back</mat-icon>
      Back to projects
    </a>

    @if (loadError()) {
      <p class="error-text" role="alert">Couldn't load this project.</p>
    } @else if (project(); as project) {
      <div class="page-header">
        <div>
          <h1>{{ project.name }}</h1>
          @if (project.description) {
            <p class="description">{{ project.description }}</p>
          }
        </div>
        <div class="header-actions">
          <button mat-stroked-button type="button" (click)="onEditProject(project)">
            <mat-icon>edit</mat-icon>
            Edit
          </button>
          <button mat-stroked-button color="warn" type="button" (click)="onDeleteProject(project)">
            <mat-icon>delete</mat-icon>
            Delete
          </button>
        </div>
      </div>

      <div class="members-header">
        <h2>Members</h2>
        <button mat-flat-button color="primary" type="button" (click)="onAddMember(project.id)">
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
              {{ member.user_display_name }}
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
                    ? 'Unset ' + member.user_display_name + ' as primary project'
                    : 'Set ' + member.user_display_name + ' as primary project'
                "
                [matTooltip]="
                  member.is_primary ? 'Primary project — click to unset' : 'Set as primary project'
                "
                (click)="onTogglePrimary(project.id, member)"
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
                matTooltip="Remove from project"
                (click)="onRemoveMember(project.id, member)"
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
export class ProjectDetail {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly projectService = inject(ProjectService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly columns = ['username', 'primary', 'actions'];

  private readonly projectId = toSignal(
    this.route.paramMap.pipe(switchMap((params) => of(params.get('id') ?? ''))),
    { initialValue: '' },
  );

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);
  private readonly projectId$ = toObservable(this.projectId);

  protected readonly project = toSignal(
    this.projectId$.pipe(
      switchMap((id) => {
        if (!id) {
          return of(undefined);
        }
        return this.projectService.get(id).pipe(
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
        const id = this.projectId();
        if (!id) {
          return of<ProjectMember[] | undefined>(undefined);
        }
        return this.projectService.listMembers(id).pipe(catchError(() => of<ProjectMember[]>([])));
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly membersLoading = computed(() => this.membersResult() === undefined);
  protected readonly members = computed(() => this.membersResult() ?? []);

  protected onEditProject(project: Project): void {
    const dialogRef = this.dialog.open(ProjectFormDialog, {
      width: '480px',
      data: { project },
    });
    dialogRef.afterClosed().subscribe((result?: ProjectFormResult) => {
      if (!result) {
        return;
      }
      this.projectService.update(project.id, result).subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onDeleteProject(project: Project): void {
    const data: ConfirmDialogData = {
      title: `Delete ${project.name}?`,
      message: `This can't be undone. It will fail if any bitza is still responsible-to this project.`,
      confirmLabel: 'Delete',
      destructive: true,
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.projectService.delete(project.id).subscribe({
        next: () => this.router.navigateByUrl('/projects'),
        error: (err: HttpErrorResponse) => {
          if (err.status === 409) {
            this.snackBar.open(
              "Can't delete — one or more bitzas are still responsible to this project.",
              'Dismiss',
              { duration: 6000 },
            );
          } else {
            this.snackBar.open('Something went wrong deleting this project.', 'Dismiss', {
              duration: 6000,
            });
          }
        },
      });
    });
  }

  protected onAddMember(projectId: string): void {
    const data: AddMemberDialogData = {
      existingMemberUserIds: this.members().map((member) => member.user_id),
    };
    const dialogRef = this.dialog.open(AddMemberDialog, { width: '480px', data });
    dialogRef.afterClosed().subscribe((result?: AddMemberResult) => {
      if (!result) {
        return;
      }
      this.projectService
        .addMember(projectId, { user_id: result.userId, is_primary: result.isPrimary })
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onTogglePrimary(projectId: string, member: ProjectMember): void {
    this.projectService
      .setPrimary(projectId, member.user_id, !member.is_primary)
      .subscribe(() => this.reload.update((n) => n + 1));
  }

  protected onRemoveMember(projectId: string, member: ProjectMember): void {
    const data: ConfirmDialogData = {
      title: 'Remove member?',
      message: `Remove ${member.user_display_name} from the project.`,
      confirmLabel: 'Remove',
      destructive: true,
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.projectService
        .removeMember(projectId, member.user_id)
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }
}
