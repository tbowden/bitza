import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, of } from 'rxjs';
import { User } from '../../../core/models';
import { UserService } from '../../../core/services/user.service';

export interface AddMemberDialogData {
  /** user_ids already on the team, so they don't show up as pickable again. */
  existingMemberUserIds: string[];
}

export interface AddMemberResult {
  userId: string;
  isPrimary: boolean;
}

@Component({
  selector: 'app-add-member-dialog',
  imports: [
    MatAutocompleteModule,
    MatButtonModule,
    MatCheckboxModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>Add member</h2>

    <mat-dialog-content>
      @if (loadError()) {
        <p class="error-text" role="alert">Couldn't load the user directory. Try again shortly.</p>
      } @else if (usersLoading()) {
        <div class="loading-row">
          <mat-progress-spinner diameter="24" mode="indeterminate"></mat-progress-spinner>
          <span>Loading users…</span>
        </div>
      } @else {
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Find a person</mat-label>
          <input
            matInput
            type="text"
            [value]="searchText()"
            (input)="onSearchInput($event)"
            [matAutocomplete]="auto"
            placeholder="Search by username or email"
          />
          <mat-autocomplete
            #auto="matAutocomplete"
            [displayWith]="displayUser"
            (optionSelected)="selectedUser.set($event.option.value)"
          >
            @for (user of filteredUsers(); track user.id) {
              <mat-option [value]="user">{{ user.username }} ({{ user.email }})</mat-option>
            }
          </mat-autocomplete>
        </mat-form-field>

        @if (selectedUser(); as user) {
          <p class="selected-user">
            Selected: <strong>{{ user.username }}</strong>
          </p>
        }

        <mat-checkbox [checked]="isPrimary()" (change)="isPrimary.set($event.checked)">
          Make this their primary team
        </mat-checkbox>
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
      <button
        mat-flat-button
        color="primary"
        type="button"
        [disabled]="!selectedUser()"
        (click)="onConfirm()"
      >
        Add
      </button>
    </mat-dialog-actions>
  `,
  styles: `
    .full-width {
      width: 100%;
    }

    .loading-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 1rem 0;
    }

    .selected-user {
      margin: 0.25rem 0 1rem;
    }

    .error-text {
      color: var(--mat-sys-error);
    }
  `,
})
export class AddMemberDialog {
  protected readonly dialogRef = inject(MatDialogRef<AddMemberDialog, AddMemberResult>);
  private readonly data = inject<AddMemberDialogData>(MAT_DIALOG_DATA);
  private readonly userService = inject(UserService);

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  private readonly allUsers = toSignal(
    this.userService.list().pipe(
      catchError(() => {
        this.loadErrorSignal.set(true);
        return of<User[]>([]);
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly usersLoading = computed(() => this.allUsers() === undefined);

  protected readonly searchText = signal('');
  protected readonly selectedUser = signal<User | null>(null);
  protected readonly isPrimary = signal(false);

  private readonly pickableUsers = computed(() => {
    const users = this.allUsers() ?? [];
    const existing = new Set(this.data.existingMemberUserIds);
    return users.filter((user) => !existing.has(user.id));
  });

  protected readonly filteredUsers = computed(() => {
    const query = this.searchText().trim().toLowerCase();
    const pickable = this.pickableUsers();
    if (!query) {
      return pickable;
    }
    return pickable.filter(
      (user) =>
        user.username.toLowerCase().includes(query) || user.email.toLowerCase().includes(query),
    );
  });

  protected displayUser(user: User | null): string {
    return user ? user.username : '';
  }

  protected onSearchInput(event: Event): void {
    this.searchText.set((event.target as HTMLInputElement).value);
    this.selectedUser.set(null);
  }

  protected onConfirm(): void {
    const user = this.selectedUser();
    if (!user) {
      return;
    }
    this.dialogRef.close({ userId: user.id, isPrimary: this.isPrimary() });
  }
}
