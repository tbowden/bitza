import { Component, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, of, switchMap } from 'rxjs';
import { CategoryService } from '../../../core/services/category.service';

@Component({
  selector: 'app-category-manager-dialog',
  imports: [
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatListModule,
  ],
  template: `
    <h2 mat-dialog-title>Manage categories</h2>

    <mat-dialog-content>
      <form class="add-row" (submit)="onAdd($event)" novalidate>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>New category name</mat-label>
          <input matInput type="text" [value]="newName()" (input)="onNewNameInput($event)" />
        </mat-form-field>
        <button
          mat-icon-button
          type="submit"
          aria-label="Add category"
          [disabled]="!newName().trim()"
        >
          <mat-icon>add</mat-icon>
        </button>
      </form>

      @if (categories().length === 0) {
        <p>No categories yet.</p>
      } @else {
        <mat-list>
          @for (category of categories(); track category.id) {
            <mat-list-item>
              <div class="category-row">
                @if (editingId() === category.id) {
                  <input
                    matInput
                    type="text"
                    class="rename-input"
                    [value]="editingName()"
                    (input)="onEditingNameInput($event)"
                    (keydown.enter)="onSaveRename(category.id)"
                  />
                  <button
                    mat-icon-button
                    type="button"
                    aria-label="Save name"
                    (click)="onSaveRename(category.id)"
                  >
                    <mat-icon>check</mat-icon>
                  </button>
                  <button
                    mat-icon-button
                    type="button"
                    aria-label="Cancel rename"
                    (click)="editingId.set(null)"
                  >
                    <mat-icon>close</mat-icon>
                  </button>
                } @else {
                  <span class="category-name">{{ category.name }}</span>
                  <button
                    mat-icon-button
                    type="button"
                    aria-label="Rename category"
                    (click)="onStartRename(category)"
                  >
                    <mat-icon>edit</mat-icon>
                  </button>
                  <button
                    mat-icon-button
                    type="button"
                    aria-label="Delete category"
                    (click)="onDelete(category.id)"
                  >
                    <mat-icon>delete</mat-icon>
                  </button>
                }
              </div>
            </mat-list-item>
          }
        </mat-list>
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button type="button" [mat-dialog-close]="true">Done</button>
    </mat-dialog-actions>
  `,
  styles: `
    .full-width {
      width: 100%;
    }

    .add-row {
      display: flex;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .rename-input {
      flex: 1;
    }

    .category-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      width: 100%;
    }

    .category-name {
      flex: 1;
    }
  `,
})
export class CategoryManagerDialog {
  private readonly categoryService = inject(CategoryService);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly newName = signal('');
  protected readonly editingId = signal<string | null>(null);
  protected readonly editingName = signal('');

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);

  protected readonly categories = toSignal(
    this.reload$.pipe(
      switchMap(() =>
        this.categoryService.list().pipe(
          catchError(() => {
            this.snackBar.open("Couldn't load categories.", 'Dismiss', { duration: 5000 });
            return of([]);
          }),
        ),
      ),
    ),
    { initialValue: [] },
  );

  protected onNewNameInput(event: Event): void {
    this.newName.set((event.target as HTMLInputElement).value);
  }

  protected onEditingNameInput(event: Event): void {
    this.editingName.set((event.target as HTMLInputElement).value);
  }

  protected onAdd(event: Event): void {
    event.preventDefault();
    const name = this.newName().trim();
    if (!name) {
      return;
    }
    this.categoryService.create({ name }).subscribe(() => {
      this.newName.set('');
      this.reload.update((n) => n + 1);
    });
  }

  protected onStartRename(category: { id: string; name: string }): void {
    this.editingId.set(category.id);
    this.editingName.set(category.name);
  }

  protected onSaveRename(id: string): void {
    const name = this.editingName().trim();
    if (!name) {
      return;
    }
    this.categoryService.update(id, { name }).subscribe(() => {
      this.editingId.set(null);
      this.reload.update((n) => n + 1);
    });
  }

  protected onDelete(id: string): void {
    this.categoryService.delete(id).subscribe({
      next: () => this.reload.update((n) => n + 1),
      error: (err: HttpErrorResponse) => {
        const message =
          err.status === 409
            ? "Can't delete — a bitza still uses this category."
            : 'Something went wrong deleting this category.';
        this.snackBar.open(message, 'Dismiss', { duration: 5000 });
      },
    });
  }
}
