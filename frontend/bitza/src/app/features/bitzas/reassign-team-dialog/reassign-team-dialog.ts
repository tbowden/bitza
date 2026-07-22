import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormField, form, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { catchError, of } from 'rxjs';
import { AppConfigService } from '../../../core/services/app-config.service';
import { TeamService } from '../../../core/services/team.service';
import { BitzaKind, CascadeScope, Team } from '../../../core/models';

export interface ReassignTeamDialogData {
  kind: BitzaKind;
  currentTeamId: string;
}

export interface ReassignTeamResult {
  teamId: string;
  cascadeScope: CascadeScope;
}

interface ReassignFormModel {
  team_id: string;
  cascade_scope: CascadeScope | '';
}

/**
 * Frontend UX default only — the backend never infers one and always
 * requires cascade_scope explicitly. See "Reassigning responsible team".
 * A cupboard (fixed) defaults to not sweeping its contents; a toolbox
 * (mobile) defaults to sweeping everything inside since the tools travel
 * with it; stock defaults to none since it rarely has children.
 */
function defaultCascadeScope(kind: BitzaKind): CascadeScope {
  return kind === 'mobile' ? 'all_descendants' : 'none';
}

@Component({
  selector: 'app-reassign-team-dialog',
  imports: [FormField, MatButtonModule, MatDialogModule, MatFormFieldModule, MatSelectModule],
  template: `
    <h2 mat-dialog-title>Reassign {{ config.teamLabelSingular().toLowerCase() }}</h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>New {{ config.teamLabelSingular().toLowerCase() }}</mat-label>
          <mat-select [formField]="reassignForm.team_id">
            @for (team of teams(); track team.id) {
              <mat-option [value]="team.id">{{ team.name }}</mat-option>
            }
          </mat-select>
          @if (reassignForm.team_id().touched() && reassignForm.team_id().invalid()) {
            <mat-error>Choose a {{ config.teamLabelSingular().toLowerCase() }}.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Apply to</mat-label>
          <mat-select [formField]="reassignForm.cascade_scope">
            <mat-option value="none">Just this bitza</mat-option>
            <mat-option value="direct_children">This bitza and its direct children</mat-option>
            <mat-option value="all_descendants"
              >This bitza and everything nested inside it</mat-option
            >
          </mat-select>
          @if (reassignForm.cascade_scope().touched() && reassignForm.cascade_scope().invalid()) {
            <mat-error>Choose how far this reassignment reaches.</mat-error>
          }
        </mat-form-field>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
        <button mat-flat-button color="primary" type="submit">Reassign</button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    .full-width {
      width: 100%;
    }
  `,
})
export class ReassignTeamDialog {
  protected readonly config = inject(AppConfigService);
  protected readonly dialogRef = inject(MatDialogRef<ReassignTeamDialog, ReassignTeamResult>);
  private readonly data = inject<ReassignTeamDialogData>(MAT_DIALOG_DATA);
  private readonly teamService = inject(TeamService);

  protected readonly teams = toSignal(
    this.teamService.list().pipe(catchError(() => of<Team[]>([]))),
    { initialValue: [] },
  );

  protected readonly model = signal<ReassignFormModel>({
    team_id: this.data.currentTeamId,
    cascade_scope: defaultCascadeScope(this.data.kind),
  });

  protected readonly reassignForm = form(this.model, (path) => {
    required(path.team_id, { message: 'Team is required' });
    required(path.cascade_scope, { message: 'Scope is required' });
  });

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.reassignForm, async () => {
      const value = this.model();
      this.dialogRef.close({
        teamId: value.team_id,
        cascadeScope: value.cascade_scope as CascadeScope,
      });
      return undefined;
    });
  }
}
