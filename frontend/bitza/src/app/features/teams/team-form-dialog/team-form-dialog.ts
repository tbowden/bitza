import { Component, inject, signal } from '@angular/core';
import { FormField, form, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { AppConfigService } from '../../../core/services/app-config.service';
import { Team } from '../../../core/models';

export interface TeamFormDialogData {
  /** Present when editing; absent when creating. */
  team?: Team;
}

export interface TeamFormResult {
  name: string;
  description: string;
}

interface TeamFormModel {
  name: string;
  description: string;
}

@Component({
  selector: 'app-team-form-dialog',
  imports: [FormField, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 mat-dialog-title>
      {{ isEdit ? 'Edit' : 'New' }} {{ config.teamLabelSingular().toLowerCase() }}
    </h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput type="text" [formField]="teamForm.name" />
          @if (teamForm.name().touched() && teamForm.name().invalid()) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Description</mat-label>
          <textarea matInput rows="3" [formField]="teamForm.description"></textarea>
        </mat-form-field>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button color="primary" type="submit">
          {{ isEdit ? 'Save' : 'Create' }}
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    .full-width {
      width: 100%;
    }
  `,
})
export class TeamFormDialog {
  protected readonly config = inject(AppConfigService);
  protected readonly dialogRef = inject(MatDialogRef<TeamFormDialog, TeamFormResult>);
  private readonly data = inject<TeamFormDialogData>(MAT_DIALOG_DATA, { optional: true });

  protected readonly isEdit = !!this.data?.team;

  protected readonly model = signal<TeamFormModel>({
    name: this.data?.team?.name ?? '',
    description: this.data?.team?.description ?? '',
  });

  protected readonly teamForm = form(this.model, (path) => {
    required(path.name, { message: 'Name is required' });
  });

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.teamForm, async () => {
      this.dialogRef.close({ ...this.model() });
      return undefined;
    });
  }
}
