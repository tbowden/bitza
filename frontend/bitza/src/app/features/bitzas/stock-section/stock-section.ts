import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, output, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSnackBar } from '@angular/material/snack-bar';
import { HttpErrorResponse } from '@angular/common/http';
import { catchError, of, switchMap } from 'rxjs';
import { StockService } from '../../../core/services/stock.service';
import { StockAdjustmentRequest, StockLog } from '../../../core/models';
import {
  StockAdjustDialog,
  StockAdjustDialogData,
} from '../stock-adjust-dialog/stock-adjust-dialog';

@Component({
  selector: 'app-stock-section',
  imports: [DatePipe, MatButtonModule, MatExpansionModule],
  template: `
    <div class="stock-actions">
      <button mat-flat-button color="primary" type="button" (click)="onAdjust()">
        Adjust stock
      </button>
    </div>

    @if (history().length > 0) {
      <mat-expansion-panel class="history-panel">
        <mat-expansion-panel-header>Stock history</mat-expansion-panel-header>
        <ul class="history-list">
          @for (entry of history(); track entry.id) {
            <li>
              {{ entry.delta > 0 ? '+' : '' }}{{ entry.delta }}
              @if (entry.note) {
                — {{ entry.note }}
              }
              ({{ entry.created_at | date: 'short' }})
            </li>
          }
        </ul>
      </mat-expansion-panel>
    }
  `,
  styles: `
    .stock-actions {
      margin-bottom: 0.75rem;
    }

    .history-list {
      margin: 0;
      padding-left: 1.25rem;
      font-size: 0.875rem;
    }
  `,
})
export class StockSection {
  readonly bitzaId = input.required<string>();
  readonly currentQuantity = input.required<number>();
  readonly adjusted = output<void>();

  private readonly stockService = inject(StockService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);
  private readonly bitzaId$ = toObservable(this.bitzaId);

  private readonly historyResult = toSignal(
    this.reload$.pipe(
      switchMap(() => this.bitzaId$),
      switchMap((id) => this.stockService.history(id).pipe(catchError(() => of<StockLog[]>([])))),
    ),
    { initialValue: [] as StockLog[] },
  );

  protected readonly history = computed(() => this.historyResult() ?? []);

  protected onAdjust(): void {
    const data: StockAdjustDialogData = { currentQuantity: this.currentQuantity() };
    const dialogRef = this.dialog.open(StockAdjustDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((result?: StockAdjustmentRequest) => {
      if (!result) {
        return;
      }
      this.stockService.adjust(this.bitzaId(), result).subscribe({
        next: () => {
          this.reload.update((n) => n + 1);
          this.adjusted.emit();
        },
        error: (err: HttpErrorResponse) => {
          const message =
            err.status === 422
              ? "That would take the quantity below zero — it wasn't applied."
              : 'Something went wrong adjusting stock.';
          this.snackBar.open(message, 'Dismiss', { duration: 6000 });
        },
      });
    });
  }
}
