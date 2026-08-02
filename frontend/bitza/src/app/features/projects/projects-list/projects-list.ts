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
import { AuthService } from '../../../core/services/auth.service';
import { ProjectService } from '../../../core/services/project.service';
import { ProjectListItem } from '../../../core/models';
import { ProjectFormDialog, ProjectFormResult } from '../project-form-dialog/project-form-dialog';

@Component({
  selector: 'app-projects-list',
  imports: [
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
  ],
  template: `
    <div class="page-header">
      <h1>Projects</h1>
      <button mat-flat-button color="primary" type="button" (click)="onCreate()">
        <mat-icon>add</mat-icon>
        New project
      </button>
    </div>

    <mat-slide-toggle [checked]="onlyMine()" (change)="onlyMine.set($event.checked)">
      Only projects I'm on
    </mat-slide-toggle>

    @if (loadError()) {
      <p class="error-text" role="alert">Couldn't load projects. Try refreshing.</p>
    } @else if (projectsLoading()) {
      <div class="loading-row">
        <mat-progress-spinner diameter="28" mode="indeterminate"></mat-progress-spinner>
      </div>
    } @else if (visibleProjects().length === 0) {
      <p>No projects to show yet.</p>
    } @else {
      <div class="project-grid">
        @for (project of visibleProjects(); track project.id) {
          <mat-card
            class="project-card"
            role="button"
            tabindex="0"
            [attr.aria-label]="'Open ' + project.name"
            (click)="openProject(project.id)"
            (keydown.enter)="openProject(project.id)"
            (keydown.space)="openProject(project.id); $event.preventDefault()"
          >
            <mat-card-header>
              <mat-card-title
                ><h2>{{ project.name }}</h2></mat-card-title
              >
            </mat-card-header>
            @if (project.member_count > 0) {
              <mat-card-content
                >{{ project.member_count }} member{{
                  project.member_count === 1 ? '' : 's'
                }}</mat-card-content
              >
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

    .project-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }

    .project-card {
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
export class ProjectsList {
  private readonly authService = inject(AuthService);
  private readonly projectService = inject(ProjectService);
  private readonly dialog = inject(MatDialog);
  private readonly router = inject(Router);

  protected readonly onlyMine = signal(false);

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);

  private readonly allProjects = toSignal(
    this.reload$.pipe(
      switchMap(() =>
        this.projectService.list().pipe(
          catchError(() => {
            this.loadErrorSignal.set(true);
            return of<ProjectListItem[]>([]);
          }),
        ),
      ),
    ),
    { initialValue: undefined },
  );

  private readonly myProjects = toSignal(
    this.reload$.pipe(
      switchMap(() => {
        const userId = this.authService.currentUser()?.id;
        if (!userId) {
          return of<ProjectListItem[]>([]);
        }
        return this.projectService.list(userId).pipe(catchError(() => of<ProjectListItem[]>([])));
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly projectsLoading = computed(() =>
    this.onlyMine() ? this.myProjects() === undefined : this.allProjects() === undefined,
  );

  protected readonly visibleProjects = computed(() => {
    const projects = this.onlyMine() ? this.myProjects() : this.allProjects();
    return projects ?? [];
  });

  protected onCreate(): void {
    const dialogRef = this.dialog.open(ProjectFormDialog, { width: '480px' });
    dialogRef.afterClosed().subscribe((result?: ProjectFormResult) => {
      if (!result) {
        return;
      }
      this.projectService.create(result).subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected openProject(projectId: string): void {
    this.router.navigate(['/projects', projectId]);
  }
}
