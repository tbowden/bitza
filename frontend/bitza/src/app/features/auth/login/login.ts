import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { FormField, form, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AuthService } from '../../../core/services/auth.service';

interface LoginCredentials {
  identifier: string;
  password: string;
}

@Component({
  selector: 'app-login',
  imports: [
    FormField,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <div class="login-page">
      <mat-card class="login-card">
        <mat-card-header>
          <mat-card-title>Bitza</mat-card-title>
          <mat-card-subtitle>Sign in to your workshop</mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          <form (submit)="onSubmit($event)" novalidate>
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Email or username</mat-label>
              <input
                matInput
                type="text"
                autocomplete="username"
                [formField]="credentialsForm.identifier"
              />
              @if (
                credentialsForm.identifier().touched() && credentialsForm.identifier().invalid()
              ) {
                <mat-error>Enter your email or username.</mat-error>
              }
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Password</mat-label>
              <input
                matInput
                type="password"
                autocomplete="current-password"
                [formField]="credentialsForm.password"
              />
              @if (credentialsForm.password().touched() && credentialsForm.password().invalid()) {
                <mat-error>Enter your password.</mat-error>
              }
            </mat-form-field>

            @if (serverError()) {
              <p class="server-error" role="alert">{{ serverError() }}</p>
            }

            <button
              mat-flat-button
              color="primary"
              type="submit"
              class="full-width submit-button"
              [disabled]="submitting()"
            >
              @if (submitting()) {
                <mat-progress-spinner
                  diameter="20"
                  mode="indeterminate"
                  aria-label="Signing in"
                ></mat-progress-spinner>
              } @else {
                Sign in
              }
            </button>
          </form>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: `
    .login-page {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      background: var(--mat-sys-surface-container-low);
    }

    .login-card {
      width: 100%;
      max-width: 380px;
    }

    .full-width {
      width: 100%;
    }

    .submit-button {
      margin-top: 0.5rem;
      height: 40px;
    }

    .server-error {
      color: var(--mat-sys-error);
      font-size: 0.875rem;
      margin: 0 0 0.75rem;
    }
  `,
})
export class Login {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly credentials = signal<LoginCredentials>({ identifier: '', password: '' });

  protected readonly credentialsForm = form(this.credentials, (path) => {
    required(path.identifier, { message: 'Enter your email or username' });
    required(path.password, { message: 'Enter your password' });
  });

  protected readonly submitting = signal(false);
  protected readonly serverError = signal<string | null>(null);

  protected async onSubmit(event: Event): Promise<void> {
    event.preventDefault();
    await submit(this.credentialsForm, async () => {
      this.submitting.set(true);
      this.serverError.set(null);
      try {
        const { identifier, password } = this.credentials();
        await firstValueFrom(this.authService.login(identifier, password));
        await this.router.navigateByUrl('/');
        return undefined;
      } catch {
        this.serverError.set('Incorrect email/username or password.');
        return undefined;
      } finally {
        this.submitting.set(false);
      }
    });
  }
}
