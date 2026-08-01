import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormField, applyWhen, form, min, required, submit } from '@angular/forms/signals';
import { MatButtonModule } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialog,
  MatDialogModule,
  MatDialogRef,
} from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable, catchError, firstValueFrom, map, of } from 'rxjs';
import { AppConfigService } from '../../../core/services/app-config.service';
import { CategoryService } from '../../../core/services/category.service';
import { CheckoutService } from '../../../core/services/checkout.service';
import { StockService } from '../../../core/services/stock.service';
import { TeamService } from '../../../core/services/team.service';
import {
  Bitza,
  BitzaCreate,
  BitzaKind,
  BitzaUpdate,
  Category,
  Checkout,
  FuzzyState,
  StockLog,
  StockMode,
  TeamListItem,
} from '../../../core/models';
import { ConfirmDialog, ConfirmDialogData } from '../../../shared/confirm-dialog/confirm-dialog';

export interface BitzaFormDialogData {
  /** Present when editing; absent (bitza) when creating. */
  bitza?: Bitza;
  /**
   * Which bitza the new one will live under. Always required for create —
   * there is no "create at root" anymore; the root bitza is created once
   * via the backend CLI, never through this dialog.
   */
  parentId?: string;
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
  /**
   * Only meaningful (and only sent) when stock_mode = 'exact' — either at
   * creation, or as the starting value when an edit genuinely transitions
   * into stock_mode='exact'. Never sent for an unchanged exact-mode edit
   * (that must go through the stock-adjustments dialog instead).
   */
  quantity: number;
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

const STOCK_MODE_LABELS: Record<StockMode, string> = {
  exact: 'Exact quantity',
  fuzzy: 'Fuzzy (plentiful / low / empty)',
};

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

        @if (isRootBitza) {
          <p class="root-readonly-note">
            This is the tree's root bitza — its name is the only field that can be changed.
          </p>
        } @else {
          @if (isEdit && kindLocked()) {
            <p class="kind-readonly">
              Type: <strong>{{ kindLabel(data?.bitza?.kind) }}</strong> (locked —
              {{ lockReason() }})
            </p>
          } @else {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Type</mat-label>
              <mat-select [formField]="bitzaForm.kind">
                @for (option of kindOptions; track option.value) {
                  <mat-option
                    [value]="option.value"
                    [disabled]="option.value === 'stock' && hasChildren"
                  >
                    {{ option.label }}
                  </mat-option>
                }
              </mat-select>
            </mat-form-field>
            @if (hasChildren) {
              <p class="kind-hint">
                Can't change to Stock — this bitza has children, and stock bitzas can't have any.
              </p>
            }
            @if (isEdit && bitzaForm.kind().value() !== data?.bitza?.kind) {
              <p class="kind-hint">
                Changing type can affect checkout or stock-tracking history views.
              </p>
            }
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
            @if (isEdit && stockModeLocked()) {
              <p class="stock-mode-readonly">
                Stock tracking: <strong>{{ stockModeLabel() }}</strong> (locked —
                {{ lockReason() }})
              </p>
            } @else {
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
            }

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

            @if (showStartingQuantity()) {
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Starting quantity</mat-label>
                <input matInput type="number" [formField]="bitzaForm.quantity" />
                @if (bitzaForm.quantity().touched() && bitzaForm.quantity().invalid()) {
                  <mat-error>Enter a starting quantity of 0 or more.</mat-error>
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

    .root-readonly-note {
      color: var(--mat-sys-on-surface-variant);
      margin: 0 0 1rem;
    }

    .stock-mode-readonly {
      color: var(--mat-sys-on-surface-variant);
      margin: 0 0 1rem;
    }

    .kind-hint {
      color: var(--mat-sys-on-surface-variant);
      font-size: 0.8125rem;
      margin: -0.5rem 0 1rem;
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
  private readonly checkoutService = inject(CheckoutService);
  private readonly stockService = inject(StockService);
  private readonly dialog = inject(MatDialog);

  protected readonly kindOptions = KIND_OPTIONS;
  protected readonly isEdit = !!this.data?.bitza;
  /**
   * Mirrors BitzaService._guard_root_bitza_update on the backend — the
   * form shows Name and nothing else for the root, rather than a
   * field-by-field locked/readonly treatment, since literally every
   * other field is off-limits there at once.
   */
  protected readonly isRootBitza = !!this.data?.bitza?.is_root;
  /**
   * Mirrors the update_bitza kind-transition guard that rejects moving
   * to 'stock' while children exist — disables that option up front
   * rather than letting the change get all the way to a 409 on submit,
   * same as the existing kindLocked/stockModeLocked checks below.
   */
  protected readonly hasChildren = this.isEdit && (this.data?.bitza?.child_count ?? 0) > 0;

  protected kindLabel(kind: BitzaKind | undefined): string {
    return kind ? (KIND_OPTIONS.find((o) => o.value === kind)?.label ?? kind) : '';
  }

  private transitionMessage(value: BitzaFormModel): string {
    const name = this.data?.bitza?.name ?? 'this bitza';
    const oldKind = this.data?.bitza?.kind;
    if (value.kind !== oldKind) {
      return (
        `Change "${name}" from ${this.kindLabel(oldKind)} to ${this.kindLabel(value.kind)}? ` +
        `Checkout and stock-tracking fields specific to the old type will be cleared.`
      );
    }
    // Same kind ('stock') — only stock_mode is moving.
    const from = STOCK_MODE_LABELS[this.data?.bitza?.stock_mode ?? 'exact'];
    const to = STOCK_MODE_LABELS[value.stock_mode as StockMode];
    return `Change how "${name}" tracks stock, from ${from} to ${to}?`;
  }

  /** True only for the one kind/stock_mode combination that can ever
   * have orphanable history: an exact-mode stock bitza (adjustments) or
   * a mobile bitza (checkouts). Fixed bitzas and fuzzy-mode stock never
   * need the check — there's nothing there to protect. */
  private needsHistoryCheck(bitza: Bitza): boolean {
    return bitza.kind === 'mobile' || (bitza.kind === 'stock' && bitza.stock_mode === 'exact');
  }

  private wasAlreadyExact(): boolean {
    return this.data?.bitza?.kind === 'stock' && this.data?.bitza?.stock_mode === 'exact';
  }

  private historyCount$(bitza: Bitza): Observable<number> {
    const rows$: Observable<Checkout[] | StockLog[]> =
      bitza.kind === 'mobile'
        ? this.checkoutService.history(bitza.id)
        : this.stockService.history(bitza.id);
    return rows$.pipe(
      map((rows) => rows.length),
      catchError(() => of(0)),
    );
  }

  /**
   * How many history rows (checkouts, or stock adjustments) exist for
   * the bitza being edited — mirrors BitzaService.update_bitza's
   * history guards on the backend, checked here too so the form can
   * lock the field and explain why up front, rather than let someone
   * fill out a whole edit only to hit a 409 on submit. undefined while
   * loading (treated as locked, the safe default) or when no check is
   * needed at all.
   */
  private readonly historyCountResult = toSignal(
    this.isEdit && this.data?.bitza && this.needsHistoryCheck(this.data.bitza)
      ? this.historyCount$(this.data.bitza)
      : of(0),
    { initialValue: undefined },
  );

  protected readonly kindLocked = computed(() => {
    const bitza = this.data?.bitza;
    if (!this.isEdit || !bitza || !this.needsHistoryCheck(bitza)) {
      return false;
    }
    const count = this.historyCountResult();
    return count === undefined || count > 0;
  });

  protected readonly stockModeLocked = computed(() => {
    if (!this.isEdit || !this.wasAlreadyExact()) {
      return false;
    }
    const count = this.historyCountResult();
    return count === undefined || count > 0;
  });

  protected readonly lockReason = computed(() => {
    const count = this.historyCountResult();
    if (count === undefined) {
      return 'checking history…';
    }
    const noun = this.data?.bitza?.kind === 'mobile' ? 'checkout' : 'stock adjustment';
    return `${count} ${noun}${count === 1 ? '' : 's'} on record`;
  });

  /** Starting-quantity input shows on create, and on edit only when
   * genuinely moving into stock_mode='exact' for the first time —
   * never while merely staying exact (that must go through
   * POST .../stock-adjustments instead). */
  protected readonly showStartingQuantity = computed(() => {
    if (
      this.bitzaForm.kind().value() !== 'stock' ||
      this.bitzaForm.stock_mode().value() !== 'exact'
    ) {
      return false;
    }
    return !this.isEdit || !this.wasAlreadyExact();
  });

  /**
   * Read-only label for edit mode — see the stock_mode-inert-during-edit
   * fix (bitza_schema_reconciliation_todo.md). Always sourced from the
   * bitza's actual persisted stock_mode, never the (now hidden) form
   * control, since that control could otherwise be flipped without the
   * change ever reaching the backend.
   */
  protected readonly stockModeLabel = computed(() => {
    const mode = this.data?.bitza?.stock_mode;
    return mode ? STOCK_MODE_LABELS[mode] : '';
  });

  protected readonly teams = toSignal(
    this.teamService.list().pipe(catchError(() => of<TeamListItem[]>([]))),
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
    quantity: this.data?.bitza?.quantity ?? 0,
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
        applyWhen(
          path,
          (ctx) =>
            ctx.valueOf(path.stock_mode) === 'exact' && (!this.isEdit || !this.wasAlreadyExact()),
          (path) => {
            required(path.quantity, { message: 'Starting quantity is required' });
            min(path.quantity, 0, { message: 'Quantity cannot be negative' });
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
        if (this.isRootBitza) {
          // Every other field is hidden above, but the model still
          // carries their prefilled defaults (e.g. the existing
          // responsible_team_id) — sending those as unchanged values
          // would still trip the "only name" guard on the backend, so
          // this is built by hand rather than reusing the general
          // update object below.
          this.dialogRef.close({ mode: 'edit', value: { name: value.name } });
          return undefined;
        }

        const update: BitzaUpdate = {
          name: value.name,
          responsible_team_id: value.responsible_team_id,
          category_id: value.category_id || null,
          description: value.description || null,
          vendor: value.vendor || undefined,
          purchase_date: value.purchase_date || undefined,
          order_url: value.order_url || undefined,
        };

        const oldKind = this.data?.bitza?.kind;
        const kindChanged = value.kind !== oldKind;
        const stockModeChanged =
          oldKind === 'stock' && value.stock_mode !== this.data?.bitza?.stock_mode;
        const isTransition = kindChanged || stockModeChanged;

        if (isTransition) {
          if (kindChanged) {
            update.kind = value.kind;
          }
          if (value.kind === 'stock') {
            update.stock_mode = value.stock_mode as StockMode;
            if (value.stock_mode === 'exact') {
              update.quantity = value.quantity;
            } else if (value.stock_mode === 'fuzzy') {
              update.fuzzy_state = value.fuzzy_state as FuzzyState;
            }
          }

          const confirmData: ConfirmDialogData = {
            title: 'Change type?',
            message: this.transitionMessage(value),
            confirmLabel: 'Change type',
          };
          const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data: confirmData });
          const confirmed = await firstValueFrom(dialogRef.afterClosed());
          if (!confirmed) {
            return undefined;
          }
        } else if (value.kind === 'stock' && value.stock_mode === 'fuzzy') {
          // No transition — just an ordinary edit of the starting fuzzy
          // state while staying in fuzzy mode.
          update.fuzzy_state = value.fuzzy_state as FuzzyState;
        }

        this.dialogRef.close({ mode: 'edit', value: update });
        return undefined;
      }

      const parentId = this.data?.parentId;
      if (!parentId) {
        // Should be unreachable — every caller that opens this dialog in
        // create mode must supply a parent now that root-level creation
        // no longer exists as a UI path. Fail loudly rather than send an
        // invalid request the backend will reject anyway.
        throw new Error('BitzaFormDialog: parentId is required to create a bitza');
      }

      const create: BitzaCreate = {
        name: value.name,
        kind: value.kind,
        parent_id: parentId,
        responsible_team_id: value.responsible_team_id,
        category_id: value.category_id || undefined,
        description: value.description || undefined,
      };
      if (value.kind === 'stock' && value.stock_mode) {
        create.stock_mode = value.stock_mode as StockMode;
        if (value.stock_mode === 'fuzzy' && value.fuzzy_state) {
          create.fuzzy_state = value.fuzzy_state as FuzzyState;
        } else if (value.stock_mode === 'exact') {
          create.quantity = value.quantity;
        }
      }
      this.dialogRef.close({ mode: 'create', value: create });
      return undefined;
    });
  }
}
