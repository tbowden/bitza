import { Component, inject, signal } from '@angular/core';
import { FormField, form, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { RetiredReason } from '../../../core/models';

export interface RetireDialogResult {
  reason: RetiredReason;
  note?: string;
}

interface RetireFormModel {
  reason: RetiredReason | '';
  note: string;
}

@Component({
  selector: 'app-retire-dialog',
  imports: [
    FormField,
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  template: `
    <h2 mat-dialog-title>Retire this bitza</h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Reason</mat-label>
          <mat-select [formField]="retireForm.reason">
            <mat-option value="lost">Lost</mat-option>
            <mat-option value="broken">Broken</mat-option>
            <mat-option value="discontinued">Discontinued (can't be reordered)</mat-option>
            <mat-option value="superseded">Superseded (replaced by a substitute)</mat-option>
          </mat-select>
          @if (retireForm.reason().touched() && retireForm.reason().invalid()) {
            <mat-error>Choose a reason.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Note (optional)</mat-label>
          <textarea matInput rows="2" [formField]="retireForm.note"></textarea>
        </mat-form-field>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button color="warn" type="submit">Retire</button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    .full-width {
      width: 100%;
    }
  `,
})
export class RetireDialog {
  protected readonly dialogRef = inject(MatDialogRef<RetireDialog, RetireDialogResult>);

  protected readonly model = signal<RetireFormModel>({ reason: '', note: '' });

  protected readonly retireForm = form(this.model, (path) => {
    required(path.reason, { message: 'Choose a reason' });
  });

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.retireForm, async () => {
      const value = this.model();
      this.dialogRef.close({
        reason: value.reason as RetiredReason,
        note: value.note || undefined,
      });
      return undefined;
    });
  }
}
