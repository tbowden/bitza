import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormField, applyWhen, form, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { catchError, of } from 'rxjs';
import { AppConfigService } from '../../../core/services/app-config.service';
import { CategoryService } from '../../../core/services/category.service';
import { TeamService } from '../../../core/services/team.service';
import {
  Bitza,
  BitzaCreate,
  BitzaKind,
  BitzaUpdate,
  Category,
  FuzzyState,
  StockMode,
  Team,
} from '../../../core/models';

export interface BitzaFormDialogData {
  /** Present when editing; absent when creating. */
  bitza?: Bitza;
  /** Creation context: which bitza this new one will live under (null = root). */
  parentId?: string | null;
  /** Pre-filled from the parent's own team, per the documented frontend responsibility. */
  defaultTeamId?: string;
}

export type BitzaFormResult =
  { mode: 'create'; value: BitzaCreate } | { mode: 'edit'; value: BitzaUpdate };

interface BitzaFormModel {
  name: string;
  kind: BitzaKind;
  responsible_team_id: string;
  category_id: string;
  description: string;
  stock_mode: StockMode | '';
  fuzzy_state: FuzzyState | '';
  vendor: string;
  purchase_date: string;
  order_url: string;
}

const KIND_OPTIONS: { value: BitzaKind; label: string }[] = [
  { value: 'fixed', label: 'Fixed (room, shelf, pegboard)' },
  { value: 'mobile', label: 'Mobile (checkoutable tool)' },
  { value: 'stock', label: 'Stock (consumable with quantity)' },
];

@Component({
  selector: 'app-bitza-form-dialog',
  imports: [
    FormField,
    MatButtonModule,
    MatDialogModule,
    MatExpansionModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ isEdit ? 'Edit bitza' : 'New bitza' }}</h2>

    <form (submit)="onSubmit($event)" novalidate>
      <mat-dialog-content>
        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput type="text" [formField]="bitzaForm.name" />
          @if (bitzaForm.name().touched() && bitzaForm.name().invalid()) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>

        @if (isEdit) {
          <p class="kind-readonly">
            Kind: <strong>{{ data?.bitza?.kind }}</strong> (fixed at creation)
          </p>
        } @else {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Kind</mat-label>
            <mat-select [formField]="bitzaForm.kind">
              @for (option of kindOptions; track option.value) {
                <mat-option [value]="option.value">{{ option.label }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>{{ config.teamLabelSingular() }} responsible</mat-label>
          <mat-select [formField]="bitzaForm.responsible_team_id">
            @for (team of teams(); track team.id) {
              <mat-option [value]="team.id">{{ team.name }}</mat-option>
            }
          </mat-select>
          @if (
            bitzaForm.responsible_team_id().touched() && bitzaForm.responsible_team_id().invalid()
          ) {
            <mat-error>{{ config.teamLabelSingular() }} is required.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Category</mat-label>
          <mat-select [formField]="bitzaForm.category_id">
            <mat-option value="">No category</mat-option>
            @for (category of categories(); track category.id) {
              <mat-option [value]="category.id">{{ category.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        @if (bitzaForm.kind().value() === 'stock') {
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Stock tracking</mat-label>
            <mat-select [formField]="bitzaForm.stock_mode">
              <mat-option value="exact">Exact quantity</mat-option>
              <mat-option value="fuzzy">Fuzzy (plentiful / low / empty)</mat-option>
            </mat-select>
            @if (bitzaForm.stock_mode().touched() && bitzaForm.stock_mode().invalid()) {
              <mat-error>Choose how this stock is tracked.</mat-error>
            }
          </mat-form-field>

          @if (bitzaForm.stock_mode().value() === 'fuzzy') {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Starting fuzzy state</mat-label>
              <mat-select [formField]="bitzaForm.fuzzy_state">
                <mat-option value="plentiful">Plentiful</mat-option>
                <mat-option value="low">Low</mat-option>
                <mat-option value="empty">Empty</mat-option>
              </mat-select>
              @if (bitzaForm.fuzzy_state().touched() && bitzaForm.fuzzy_state().invalid()) {
                <mat-error>Starting state is required.</mat-error>
              }
            </mat-form-field>
          }
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Description</mat-label>
          <textarea matInput rows="2" [formField]="bitzaForm.description"></textarea>
        </mat-form-field>

        @if (isEdit) {
          <mat-expansion-panel class="acquisition-panel">
            <mat-expansion-panel-header>Acquisition details</mat-expansion-panel-header>
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Vendor</mat-label>
              <input matInput type="text" [formField]="bitzaForm.vendor" />
            </mat-form-field>
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Purchase date</mat-label>
              <input
                matInput
                type="text"
                placeholder="e.g. 2026-03-14"
                [formField]="bitzaForm.purchase_date"
              />
            </mat-form-field>
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Order URL</mat-label>
              <input matInput type="text" [formField]="bitzaForm.order_url" />
            </mat-form-field>
          </mat-expansion-panel>
        }
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
      margin-bottom: 0.25rem;
    }

    .kind-readonly {
      color: var(--mat-sys-on-surface-variant);
      margin: 0 0 1rem;
    }

    .acquisition-panel {
      margin-top: 0.5rem;
    }
  `,
})
export class BitzaFormDialog {
  protected readonly config = inject(AppConfigService);
  protected readonly dialogRef = inject(MatDialogRef<BitzaFormDialog, BitzaFormResult>);
  protected readonly data = inject<BitzaFormDialogData>(MAT_DIALOG_DATA, { optional: true });
  private readonly teamService = inject(TeamService);
  private readonly categoryService = inject(CategoryService);

  protected readonly kindOptions = KIND_OPTIONS;
  protected readonly isEdit = !!this.data?.bitza;

  protected readonly teams = toSignal(
    this.teamService.list().pipe(catchError(() => of<Team[]>([]))),
    {
      initialValue: [],
    },
  );

  protected readonly categories = toSignal(
    this.categoryService.list().pipe(catchError(() => of<Category[]>([]))),
    { initialValue: [] },
  );

  protected readonly model = signal<BitzaFormModel>({
    name: this.data?.bitza?.name ?? '',
    kind: this.data?.bitza?.kind ?? 'fixed',
    responsible_team_id: this.data?.bitza?.responsible_team_id ?? this.data?.defaultTeamId ?? '',
    category_id: this.data?.bitza?.category_id ?? '',
    description: this.data?.bitza?.description ?? '',
    stock_mode: this.data?.bitza?.stock_mode ?? '',
    fuzzy_state: this.data?.bitza?.fuzzy_state ?? '',
    vendor: this.data?.bitza?.vendor ?? '',
    purchase_date: this.data?.bitza?.purchase_date ?? '',
    order_url: this.data?.bitza?.order_url ?? '',
  });

  protected readonly bitzaForm = form(this.model, (path) => {
    required(path.name, { message: 'Name is required' });
    required(path.responsible_team_id, { message: 'Responsible team is required' });

    applyWhen(
      path,
      (ctx) => ctx.valueOf(path.kind) === 'stock',
      (path) => {
        required(path.stock_mode, { message: 'Stock mode is required' });
        applyWhen(
          path,
          (ctx) => ctx.valueOf(path.stock_mode) === 'fuzzy',
          (path) => {
            required(path.fuzzy_state, { message: 'Starting state is required' });
          },
        );
      },
    );
  });

  protected onSubmit(event: Event): void {
    event.preventDefault();
    submit(this.bitzaForm, async () => {
      const value = this.model();

      if (this.isEdit) {
        const update: BitzaUpdate = {
          name: value.name,
          responsible_team_id: value.responsible_team_id,
          category_id: value.category_id || null,
          description: value.description || null,
          vendor: value.vendor || undefined,
          purchase_date: value.purchase_date || undefined,
          order_url: value.order_url || undefined,
        };
        if (value.kind === 'stock' && value.stock_mode === 'fuzzy') {
          update.fuzzy_state = value.fuzzy_state as FuzzyState;
        }
        this.dialogRef.close({ mode: 'edit', value: update });
        return undefined;
      }

      const create: BitzaCreate = {
        name: value.name,
        kind: value.kind,
        parent_id: this.data?.parentId ?? null,
        responsible_team_id: value.responsible_team_id,
        category_id: value.category_id || undefined,
        description: value.description || undefined,
      };
      if (value.kind === 'stock' && value.stock_mode) {
        create.stock_mode = value.stock_mode as StockMode;
        if (value.stock_mode === 'fuzzy' && value.fuzzy_state) {
          create.fuzzy_state = value.fuzzy_state as FuzzyState;
        }
      }
      this.dialogRef.close({ mode: 'create', value: create });
      return undefined;
    });
  }
}
