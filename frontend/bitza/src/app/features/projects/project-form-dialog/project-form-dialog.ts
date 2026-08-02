import { Component, inject, signal } from '@angular/core';
import { FormField, form, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { Project } from '../../../core/models';

export interface ProjectFormDialogData {
  /** Present when editing; absent when creating. */
  project?: Project;
}

export interface ProjectFormResult {
  name: string;
  description: string;
}

interface ProjectFormModel {
  name: string;
  description: string;
}

@Component({
  selector: 'app-project-form-dialog',
  imports: [FormField, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 mat-dialog-title>{{ isEdit ? 'Edit' : 'New' }} project</h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput type="text" [formField]="projectForm.name" />
          @if (projectForm.name().touched() && projectForm.name().invalid()) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Description</mat-label>
          <textarea matInput rows="3" [formField]="projectForm.description"></textarea>
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
export class ProjectFormDialog {
  protected readonly dialogRef = inject(MatDialogRef<ProjectFormDialog, ProjectFormResult>);
  private readonly data = inject<ProjectFormDialogData>(MAT_DIALOG_DATA, { optional: true });

  protected readonly isEdit = !!this.data?.project;

  protected readonly model = signal<ProjectFormModel>({
    name: this.data?.project?.name ?? '',
    description: this.data?.project?.description ?? '',
  });

  protected readonly projectForm = form(this.model, (path) => {
    required(path.name, { message: 'Name is required' });
  });

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.projectForm, async () => {
      this.dialogRef.close({ ...this.model() });
      return undefined;
    });
  }
}
