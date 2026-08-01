import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { catchError, of, switchMap } from 'rxjs';
import { AuthService } from '../../../core/services/auth.service';
import { CheckoutService } from '../../../core/services/checkout.service';
import { TeamService } from '../../../core/services/team.service';
import { CheckinRequest, MyCheckout, MyTeamMembership } from '../../../core/models';
import { CheckinDialog } from '../../bitzas/checkin-dialog/checkin-dialog';

/**
 * The '/me' personal landing page — "what you have checked out" and
 * "what teams you're on", pulled from GET /checkouts/mine and
 * GET /teams/mine respectively. Both endpoints are always scoped to
 * the caller server-side, so this component never passes a user id
 * anywhere.
 */
@Component({
  selector: 'app-me-page',
  imports: [
    DatePipe,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
  ],
  template: `
    <h1>{{ user()?.display_name ?? 'Me' }}</h1>

    <section aria-labelledby="checkouts-heading">
      <h2 id="checkouts-heading">Checked out to you</h2>

      @if (checkoutsError()) {
        <p class="error-text" role="alert">Couldn't load your checkouts. Try refreshing.</p>
      } @else if (checkoutsLoading()) {
        <div class="loading-row">
          <mat-progress-spinner diameter="28" mode="indeterminate"></mat-progress-spinner>
        </div>
      } @else if (checkouts().length === 0) {
        <p>Nothing checked out to you right now.</p>
      } @else {
        <div class="checkout-grid">
          @for (checkout of checkouts(); track checkout.id) {
            <mat-card class="checkout-card">
              <mat-card-header>
                <mat-card-title>
                  <h3>
                    <a [routerLink]="['/bitzas', checkout.bitza_id]">{{ checkout.bitza_name }}</a>
                  </h3>
                </mat-card-title>
                @if (checkout.bitza_kind) {
                  <mat-card-subtitle>
                    <span class="kind-tag">{{ checkout.bitza_kind }}</span>
                  </mat-card-subtitle>
                }
              </mat-card-header>
              <mat-card-content>
                <p>
                  Checked out since {{ checkout.checked_out_at | date: 'medium' }}
                  @if (checkout.team_context) {
                    for <strong>{{ checkout.team_context }}</strong>
                  }
                </p>
                @if (checkout.note) {
                  <p class="checkout-note">{{ checkout.note }}</p>
                }
              </mat-card-content>
              <mat-card-actions>
                <button mat-button type="button" (click)="onCheckin(checkout)">Check in</button>
              </mat-card-actions>
            </mat-card>
          }
        </div>
      }
    </section>

    <section aria-labelledby="teams-heading">
      <h2 id="teams-heading">Projects you're on</h2>

      @if (membershipsError()) {
        <p class="error-text" role="alert">Couldn't load your projects. Try refreshing.</p>
      } @else if (membershipsLoading()) {
        <div class="loading-row">
          <mat-progress-spinner diameter="28" mode="indeterminate"></mat-progress-spinner>
        </div>
      } @else if (memberships().length === 0) {
        <p>You're not on any projects yet.</p>
      } @else {
        <ul class="team-list">
          @for (membership of memberships(); track membership.team_id) {
            <li>
              <a [routerLink]="['/teams', membership.team_id]">{{ membership.team_name }}</a>
              @if (membership.is_primary) {
                <mat-icon
                  class="primary-star"
                  aria-label="Your primary project"
                  matTooltip="Primary project"
                  >star</mat-icon
                >
              }
            </li>
          }
        </ul>
      }
    </section>
  `,
  styles: `
    section {
      margin-bottom: 2rem;
    }

    .checkout-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
    }

    .checkout-card mat-card-title h3 {
      margin: 0;
      font: inherit;
    }

    .kind-tag {
      display: inline-block;
      padding: 0.1rem 0.5rem;
      border-radius: 1rem;
      background: var(--mat-sys-secondary-container);
      color: var(--mat-sys-on-secondary-container);
      font-size: 0.75rem;
      text-transform: capitalize;
    }

    .checkout-note {
      color: var(--mat-sys-on-surface-variant);
      font-size: 0.875rem;
    }

    .team-list {
      list-style: none;
      margin: 1rem 0 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .team-list li {
      display: flex;
      align-items: center;
      gap: 0.375rem;
    }

    .primary-star {
      color: var(--mat-sys-primary);
      font-size: 1.1rem;
      height: 1.1rem;
      width: 1.1rem;
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
export class MePage {
  private readonly authService = inject(AuthService);
  private readonly checkoutService = inject(CheckoutService);
  private readonly teamService = inject(TeamService);
  private readonly dialog = inject(MatDialog);

  protected readonly user = this.authService.currentUser;

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);

  private readonly checkoutsErrorSignal = signal(false);
  protected readonly checkoutsError = this.checkoutsErrorSignal.asReadonly();

  private readonly checkoutsResult = toSignal(
    this.reload$.pipe(
      switchMap(() =>
        this.checkoutService.listMine().pipe(
          catchError(() => {
            this.checkoutsErrorSignal.set(true);
            return of<MyCheckout[]>([]);
          }),
        ),
      ),
    ),
    { initialValue: undefined },
  );

  protected readonly checkoutsLoading = computed(() => this.checkoutsResult() === undefined);
  protected readonly checkouts = computed(() => this.checkoutsResult() ?? []);

  private readonly membershipsErrorSignal = signal(false);
  protected readonly membershipsError = this.membershipsErrorSignal.asReadonly();

  private readonly membershipsResult = toSignal(
    this.reload$.pipe(
      switchMap(() =>
        this.teamService.listMine().pipe(
          catchError(() => {
            this.membershipsErrorSignal.set(true);
            return of<MyTeamMembership[]>([]);
          }),
        ),
      ),
    ),
    { initialValue: undefined },
  );

  protected readonly membershipsLoading = computed(() => this.membershipsResult() === undefined);
  protected readonly memberships = computed(() => this.membershipsResult() ?? []);

  protected onCheckin(checkout: MyCheckout): void {
    const dialogRef = this.dialog.open(CheckinDialog, { width: '420px' });
    dialogRef.afterClosed().subscribe((result?: CheckinRequest) => {
      if (!result) {
        return;
      }
      this.checkoutService
        .checkin(checkout.bitza_id, result)
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }
}
