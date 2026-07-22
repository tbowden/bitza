import { Component, inject, signal } from '@angular/core';
import { FormField, form, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { CheckoutRequest } from '../../../core/models';

interface CheckoutFormModel {
  team_context: string;
  note: string;
}

@Component({
  selector: 'app-checkout-dialog',
  imports: [FormField, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 mat-dialog-title>Check out</h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Team (optional)</mat-label>
          <input matInput type="text" [formField]="checkoutForm.team_context" />
          <mat-hint>Leave blank to use your primary team automatically.</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Note (optional)</mat-label>
          <textarea matInput rows="2" [formField]="checkoutForm.note"></textarea>
        </mat-form-field>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button color="primary" type="submit">Check out</button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    .full-width {
      width: 100%;
    }
  `,
})
export class CheckoutDialog {
  protected readonly dialogRef = inject(MatDialogRef<CheckoutDialog, CheckoutRequest>);

  protected readonly model = signal<CheckoutFormModel>({ team_context: '', note: '' });
  protected readonly checkoutForm = form(this.model);

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.checkoutForm, async () => {
      const value = this.model();
      this.dialogRef.close({
        team_context: value.team_context || undefined,
        note: value.note || undefined,
      });
      return undefined;
    });
  }
}
