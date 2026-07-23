import { Component, computed, inject, signal } from '@angular/core';
import { FormField, applyWhen, form, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { AuthService } from '../../../core/services/auth.service';
import { AdminUserUpdate, User, UserCreate, UserRole } from '../../../core/models';

export interface UserFormDialogData {
  /** Present when editing; absent when creating. */
  user?: User;
}

export type UserFormResult =
  { mode: 'create'; value: UserCreate } | { mode: 'edit'; value: AdminUserUpdate };

interface UserFormModel {
  email: string;
  username: string;
  password: string;
  role: UserRole;
  is_suspended: boolean;
}

@Component({
  selector: 'app-user-form-dialog',
  imports: [
    FormField,
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
  ],
  templateUrl: './user-form-dialog.html',
  styleUrl: './user-form-dialog.scss',
})
export class UserFormDialog {
  protected readonly authService = inject(AuthService);
  protected readonly dialogRef = inject(MatDialogRef<UserFormDialog, UserFormResult>);
  protected readonly data = inject<UserFormDialogData>(MAT_DIALOG_DATA, { optional: true });

  protected readonly isEdit = !!this.data?.user;

  /**
   * Only a superuser can create/promote to admin; the "create admin"
   * option is itself superuser-only per the User roles permission table.
   * Creating another superuser isn't exposed here at all — deliberately
   * not a documented UI flow, treated as sensitive enough to need a more
   * manual process.
   */
  protected readonly availableRoles = computed<UserRole[]>(() =>
    this.authService.isSuperuser() ? ['user', 'admin'] : ['user'],
  );

  /** Role changes are superuser-only; admins never see the control. */
  protected readonly canChangeRole = computed(() => this.authService.isSuperuser());

  /**
   * Suspend/delete controls are superuser-only OR admin-acting-on-a-plain-user
   * per the User roles permission table ("Suspend / delete user controls" row) —
   * a different, wider rule than role-change, which stays superuser-only.
   */
  protected readonly canToggleSuspension = computed(() => {
    if (this.authService.isSuperuser()) {
      return true;
    }
    return this.authService.isAdmin() && this.data?.user?.role === 'user';
  });

  protected readonly model = signal<UserFormModel>({
    email: this.data?.user?.email ?? '',
    username: this.data?.user?.username ?? '',
    password: '',
    role: this.data?.user?.role ?? 'user',
    is_suspended: this.data?.user?.is_suspended ?? false,
  });

  protected readonly userForm = form(this.model, (path) => {
    required(path.email, { message: 'Email is required' });
    required(path.username, { message: 'Username is required' });

    applyWhen(
      path,
      () => !this.isEdit,
      (path) => {
        required(path.password, { message: 'Password is required' });
      },
    );
  });

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.userForm, async () => {
      const value = this.model();

      if (this.isEdit) {
        const update: AdminUserUpdate = {
          email: value.email,
          username: value.username,
        };
        if (this.canChangeRole()) {
          update.role = value.role;
        }
        if (this.canToggleSuspension()) {
          update.is_suspended = value.is_suspended;
        }
        this.dialogRef.close({ mode: 'edit', value: update });
        return undefined;
      }

      const create: UserCreate = {
        email: value.email,
        username: value.username,
        password: value.password,
        role: this.authService.isSuperuser() ? value.role : 'user',
      };
      this.dialogRef.close({ mode: 'create', value: create });
      return undefined;
    });
  }
}
