import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, forkJoin, map, of, switchMap } from 'rxjs';
import { CheckoutService } from '../../../core/services/checkout.service';
import { UserService } from '../../../core/services/user.service';
import { CheckinRequest, Checkout, CheckoutRequest } from '../../../core/models';
import { CheckinDialog } from '../checkin-dialog/checkin-dialog';
import { CheckoutDialog } from '../checkout-dialog/checkout-dialog';

@Component({
  selector: 'app-checkout-section',
  imports: [DatePipe, MatButtonModule, MatExpansionModule, MatProgressSpinnerModule],
  template: `
    <div class="checkout-status">
      @if (loading()) {
        <mat-progress-spinner diameter="24" mode="indeterminate"></mat-progress-spinner>
      } @else if (currentCheckout(); as checkout) {
        <p>
          Checked out by <strong>{{ holderName(checkout.user_id) }}</strong>
          @if (checkout.team_context) {
            for <strong>{{ checkout.team_context }}</strong>
          }
          since {{ checkout.checked_out_at | date: 'medium' }}.
        </p>
        @if (checkout.note) {
          <p class="checkout-note">{{ checkout.note }}</p>
        }
        <button mat-flat-button color="primary" type="button" (click)="onCheckin()">
          Check in
        </button>
      } @else {
        <p>Available.</p>
        <button mat-flat-button color="primary" type="button" (click)="onCheckout()">
          Check out
        </button>
      }
    </div>

    @if (pastCheckouts().length > 0) {
      <mat-expansion-panel class="history-panel">
        <mat-expansion-panel-header>Checkout history</mat-expansion-panel-header>
        <ul class="history-list">
          @for (entry of pastCheckouts(); track entry.id) {
            <li>
              {{ holderName(entry.user_id) }}
              @if (entry.team_context) {
                — {{ entry.team_context }}
              }
              : {{ entry.checked_out_at | date: 'short' }} →
              {{ entry.checked_in_at | date: 'short' }}
            </li>
          }
        </ul>
      </mat-expansion-panel>
    }
  `,
  styles: `
    .checkout-status {
      margin-bottom: 0.75rem;
    }

    .checkout-note {
      color: var(--mat-sys-on-surface-variant);
      font-size: 0.875rem;
    }

    .history-list {
      margin: 0;
      padding-left: 1.25rem;
      font-size: 0.875rem;
    }
  `,
})
export class CheckoutSection {
  readonly bitzaId = input.required<string>();

  private readonly checkoutService = inject(CheckoutService);
  private readonly userService = inject(UserService);
  private readonly dialog = inject(MatDialog);

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);
  private readonly bitzaId$ = toObservable(this.bitzaId);

  private readonly historyResult = toSignal(
    this.reload$.pipe(
      switchMap(() => this.bitzaId$),
      switchMap((id) =>
        this.checkoutService.history(id).pipe(catchError(() => of<Checkout[]>([]))),
      ),
    ),
    { initialValue: undefined },
  );

  protected readonly loading = computed(() => this.historyResult() === undefined);
  private readonly history = computed(() => this.historyResult() ?? []);

  protected readonly currentCheckout = computed(
    () => this.history().find((entry) => entry.checked_in_at === null) ?? null,
  );

  protected readonly pastCheckouts = computed(() =>
    this.history().filter((entry) => entry.checked_in_at !== null),
  );

  private readonly userNames = toSignal(
    toObservable(this.history).pipe(
      switchMap((entries) => {
        const ids = [...new Set(entries.map((entry) => entry.user_id))];
        if (ids.length === 0) {
          return of(new Map<string, string>());
        }
        return forkJoin(
          ids.map((id) => this.userService.get(id).pipe(catchError(() => of(null)))),
        ).pipe(
          map(
            (users) =>
              new Map(
                users
                  .filter((user): user is NonNullable<typeof user> => user !== null)
                  .map((user) => [user.id, user.username]),
              ),
          ),
        );
      }),
    ),
    { initialValue: new Map<string, string>() },
  );

  protected holderName(userId: string): string {
    return this.userNames().get(userId) ?? userId;
  }

  protected onCheckout(): void {
    const dialogRef = this.dialog.open(CheckoutDialog, { width: '420px' });
    dialogRef.afterClosed().subscribe((result?: CheckoutRequest) => {
      if (!result) {
        return;
      }
      this.checkoutService
        .checkout(this.bitzaId(), result)
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onCheckin(): void {
    const dialogRef = this.dialog.open(CheckinDialog, { width: '420px' });
    dialogRef.afterClosed().subscribe((result?: CheckinRequest) => {
      if (!result) {
        return;
      }
      this.checkoutService
        .checkin(this.bitzaId(), result)
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }
}
