import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
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
import { AuthService } from '../../../core/services/auth.service';
import { UserService } from '../../../core/services/user.service';
import { User } from '../../../core/models';
import { ConfirmDialog, ConfirmDialogData } from '../../../shared/confirm-dialog/confirm-dialog';
import {
  UserFormDialog,
  UserFormDialogData,
  UserFormResult,
} from '../user-form-dialog/user-form-dialog';

@Component({
  selector: 'app-users-list',
  imports: [
    MatButtonModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule,
    MatTooltipModule,
  ],
  templateUrl: './users-list.html',
  styleUrl: './users-list.scss',
})
export class UsersList {
  protected readonly authService = inject(AuthService);
  private readonly userService = inject(UserService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly columns = ['username', 'role', 'status', 'actions'];

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);

  private readonly usersResult = toSignal(
    this.reload$.pipe(
      switchMap(() =>
        this.userService.list().pipe(
          catchError(() => {
            this.loadErrorSignal.set(true);
            return of<User[]>([]);
          }),
        ),
      ),
    ),
    { initialValue: undefined },
  );

  protected readonly loading = computed(() => this.usersResult() === undefined);
  protected readonly users = computed(() => this.usersResult() ?? []);

  /** Matches the User roles permission table's "Suspend / delete user controls" row. */
  protected canManage(user: User): boolean {
    if (user.id === this.authService.currentUser()?.id) {
      return false;
    }
    if (this.authService.isSuperuser()) {
      return true;
    }
    return this.authService.isAdmin() && user.role === 'user';
  }

  protected onCreate(): void {
    const dialogRef = this.dialog.open(UserFormDialog, { width: '480px' });
    dialogRef.afterClosed().subscribe((result?: UserFormResult) => {
      if (!result || result.mode !== 'create') {
        return;
      }
      this.userService.create(result.value).subscribe({
        next: () => this.reload.update((n) => n + 1),
        error: (err: HttpErrorResponse) => this.showSaveError(err),
      });
    });
  }

  protected onEdit(user: User): void {
    const data: UserFormDialogData = { user };
    const dialogRef = this.dialog.open(UserFormDialog, { width: '480px', data });
    dialogRef.afterClosed().subscribe((result?: UserFormResult) => {
      if (!result || result.mode !== 'edit') {
        return;
      }
      this.userService.adminUpdate(user.id, result.value).subscribe({
        next: () => this.reload.update((n) => n + 1),
        error: (err: HttpErrorResponse) => this.showSaveError(err),
      });
    });
  }

  protected onToggleSuspend(user: User): void {
    const action = user.is_suspended ? 'unsuspend' : 'suspend';
    const data: ConfirmDialogData = {
      title: `${user.is_suspended ? 'Unsuspend' : 'Suspend'} ${user.username}?`,
      message: user.is_suspended
        ? 'They will be able to sign in again.'
        : "They won't be able to sign in until unsuspended.",
      confirmLabel: action === 'suspend' ? 'Suspend' : 'Unsuspend',
      destructive: action === 'suspend',
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.userService
        .adminUpdate(user.id, { is_suspended: !user.is_suspended })
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onDelete(user: User): void {
    const data: ConfirmDialogData = {
      title: `Delete ${user.username}?`,
      message: "This can't be undone.",
      confirmLabel: 'Delete',
      destructive: true,
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.userService.delete(user.id).subscribe({
        next: () => this.reload.update((n) => n + 1),
        error: () =>
          this.snackBar.open('Something went wrong deleting this user.', 'Dismiss', {
            duration: 6000,
          }),
      });
    });
  }

  private showSaveError(err: HttpErrorResponse): void {
    const message =
      err.status === 422 ? 'Check the form for errors.' : 'Something went wrong saving this user.';
    this.snackBar.open(message, 'Dismiss', { duration: 6000 });
  }
}
