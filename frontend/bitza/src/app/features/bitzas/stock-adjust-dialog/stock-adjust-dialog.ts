import { Component, computed, inject, signal } from '@angular/core';
import { FormField, form, min, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { StockAdjustmentRequest } from '../../../core/models';

export interface StockAdjustDialogData {
  currentQuantity: number;
}

type Direction = 'in' | 'out';

interface StockAdjustFormModel {
  direction: Direction;
  magnitude: number;
  note: string;
}

@Component({
  selector: 'app-stock-adjust-dialog',
  imports: [
    FormField,
    MatButtonModule,
    MatButtonToggleModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  template: `
    <h2 mat-dialog-title>Adjust stock</h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <p>
          Current quantity: <strong>{{ data.currentQuantity }}</strong>
        </p>

        <mat-button-toggle-group
          class="direction-toggle"
          [value]="model().direction"
          (change)="onDirectionChange($event.value)"
          aria-label="Stock direction"
        >
          <mat-button-toggle value="in">Stock in</mat-button-toggle>
          <mat-button-toggle value="out">Stock out</mat-button-toggle>
        </mat-button-toggle-group>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Amount</mat-label>
          <input matInput type="number" [formField]="adjustForm.magnitude" />
          @if (adjustForm.magnitude().touched() && adjustForm.magnitude().invalid()) {
            <mat-error>Enter an amount of at least 1.</mat-error>
          }
        </mat-form-field>

        @if (resultingQuantity() < 0) {
          <p class="error-text" role="alert">
            That would take the quantity below zero — reduce the amount.
          </p>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Note (optional)</mat-label>
          <textarea matInput rows="2" [formField]="adjustForm.note"></textarea>
        </mat-form-field>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button color="primary" type="submit" [disabled]="resultingQuantity() < 0">
          Save
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    .full-width {
      width: 100%;
    }

    .direction-toggle {
      display: flex;
      margin-bottom: 1rem;
    }

    .error-text {
      color: var(--mat-sys-error);
    }
  `,
})
export class StockAdjustDialog {
  protected readonly dialogRef = inject(MatDialogRef<StockAdjustDialog, StockAdjustmentRequest>);
  protected readonly data = inject<StockAdjustDialogData>(MAT_DIALOG_DATA);

  protected readonly model = signal<StockAdjustFormModel>({
    direction: 'in',
    magnitude: 1,
    note: '',
  });

  protected readonly adjustForm = form(this.model, (path) => {
    required(path.magnitude, { message: 'Amount is required' });
    min(path.magnitude, 1, { message: 'Must be at least 1' });
  });

  protected readonly resultingQuantity = computed(() => {
    const { direction, magnitude } = this.model();
    const signedDelta = direction === 'out' ? -Math.abs(magnitude || 0) : Math.abs(magnitude || 0);
    return this.data.currentQuantity + signedDelta;
  });

  protected onDirectionChange(direction: Direction): void {
    this.model.update((current) => ({ ...current, direction }));
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.adjustForm, async () => {
      const { direction, magnitude, note } = this.model();
      const delta = direction === 'out' ? -Math.abs(magnitude) : Math.abs(magnitude);
      this.dialogRef.close({ delta, note: note || undefined });
      return undefined;
    });
  }
}
