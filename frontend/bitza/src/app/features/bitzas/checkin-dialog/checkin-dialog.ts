import { Component, inject, signal } from '@angular/core';
import { FormField, form, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { CheckinRequest } from '../../../core/models';

interface CheckinFormModel {
  note: string;
}

@Component({
  selector: 'app-checkin-dialog',
  imports: [FormField, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 mat-dialog-title>Check in</h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Note (optional)</mat-label>
          <textarea
            matInput
            rows="2"
            placeholder="e.g. found lying around, returning it"
            [formField]="checkinForm.note"
          ></textarea>
        </mat-form-field>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button color="primary" type="submit">Check in</button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    .full-width {
      width: 100%;
    }
  `,
})
export class CheckinDialog {
  protected readonly dialogRef = inject(MatDialogRef<CheckinDialog, CheckinRequest>);

  protected readonly model = signal<CheckinFormModel>({ note: '' });
  protected readonly checkinForm = form(this.model);

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.checkinForm, async () => {
      const value = this.model();
      this.dialogRef.close({ note: value.note || undefined });
      return undefined;
    });
  }
}
