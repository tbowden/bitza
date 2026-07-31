import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { combineLatest, catchError, map, of, switchMap } from 'rxjs';
import { AppConfigService } from '../../../core/services/app-config.service';
import { AuthService } from '../../../core/services/auth.service';
import { BitzaService } from '../../../core/services/bitza.service';
import { CategoryService } from '../../../core/services/category.service';
import { TeamService } from '../../../core/services/team.service';
import {
  Bitza,
  BitzaAncestor,
  BitzaKind,
  BitzaListItem,
  BitzaListParams,
  BitzaStatus,
  Category,
  TeamListItem,
} from '../../../core/models';
import { ConfirmDialog, ConfirmDialogData } from '../../../shared/confirm-dialog/confirm-dialog';
import {
  BitzaFormDialog,
  BitzaFormDialogData,
  BitzaFormResult,
} from '../bitza-form-dialog/bitza-form-dialog';
import { CategoryManagerDialog } from '../category-manager-dialog/category-manager-dialog';
import {
  ReassignTeamDialog,
  ReassignTeamDialogData,
  ReassignTeamResult,
} from '../reassign-team-dialog/reassign-team-dialog';
import { RetireDialog, RetireDialogResult } from '../retire-dialog/retire-dialog';
import {
  MoveBitzaDialog,
  MoveBitzaDialogData,
  MoveBitzaResult,
} from '../move-bitza-dialog/move-bitza-dialog';
import { BitzaLabelDialog, BitzaLabelDialogData } from '../bitza-label-dialog/bitza-label-dialog';
import { CheckoutSection } from '../checkout-section/checkout-section';
import { StockSection } from '../stock-section/stock-section';
import { ImageGallery } from '../image-gallery/image-gallery';

@Component({
  selector: 'app-bitza-browser',
  imports: [
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatMenuModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatTableModule,
    CheckoutSection,
    StockSection,
    ImageGallery,
  ],
  template: `
    <nav class="breadcrumb" aria-label="Bitza location">
      <a routerLink="/bitzas">Home</a>
      @for (ancestor of breadcrumb(); track ancestor.id) {
        <span class="breadcrumb-sep">/</span>
        <a [routerLink]="['/bitzas', ancestor.id]">{{ ancestor.name }}</a>
      }
    </nav>

    @if (loadError()) {
      <p class="error-text" role="alert">Couldn't load this bitza.</p>
    } @else if (!currentId()) {
      <h1>Not set up yet</h1>
      <p>
        This deployment doesn't have a root bitza yet — everything in Bitza lives under one
        permanent top-level container, created once by an administrator via the backend's
        <code>create-root</code> command. Once that's done, this page will take you straight there.
      </p>
    } @else {
      @if (currentBitza(); as bitza) {
        <mat-card class="bitza-card">
          <mat-card-header>
            <mat-card-title
              ><h1>{{ bitza.name }}</h1></mat-card-title
            >
            <mat-card-subtitle>
              @if (bitza.is_root) {
                <span class="bitza-tag root-tag">root</span>
              }
              <span class="bitza-tag">{{ bitza.kind }}</span>
              @if (bitza.status === 'retired') {
                <span class="bitza-tag retired-tag">retired — {{ bitza.retired_reason }}</span>
              }
            </mat-card-subtitle>
          </mat-card-header>

          <mat-card-content>
            @if (bitza.description) {
              <p>{{ bitza.description }}</p>
            }
            <p>
              {{ config.teamLabelSingular() }} responsible:
              <strong>{{ bitza.responsible_team_name }}</strong>
            </p>
            @if (bitza.category_id) {
              <p>Category: {{ bitza.category_name }}</p>
            }
            @if (bitza.kind === 'stock') {
              <p>
                Stock:
                @if (bitza.stock_mode === 'exact') {
                  <strong>{{ bitza.quantity ?? 0 }}</strong>
                } @else {
                  <strong>{{ bitza.fuzzy_state }}</strong>
                }
              </p>
            }

            @if (bitza.kind === 'mobile') {
              <div class="action-section">
                <app-checkout-section [bitzaId]="bitza.id" />
              </div>
            }

            @if (bitza.kind === 'stock' && bitza.stock_mode === 'exact') {
              <div class="action-section">
                <app-stock-section
                  [bitzaId]="bitza.id"
                  [currentQuantity]="bitza.quantity ?? 0"
                  (adjusted)="onStockAdjusted()"
                />
              </div>
            }

            <div class="action-section">
              <app-image-gallery [bitzaId]="bitza.id" [bitzaName]="bitza.name" />
            </div>
          </mat-card-content>

          <mat-card-actions>
            <button mat-button type="button" (click)="onCreateChild(bitza)">
              <mat-icon>add</mat-icon>
              Add here
            </button>
            <button mat-button type="button" (click)="onEdit(bitza)">
              <mat-icon>edit</mat-icon>
              Edit
            </button>
            <button mat-button type="button" (click)="onViewLabel(bitza)">
              <mat-icon>qr_code_2</mat-icon>
              Label
            </button>
            <button mat-button type="button" (click)="onReassignTeam(bitza)">
              <mat-icon>swap_horiz</mat-icon>
              Reassign {{ config.teamLabelSingular().toLowerCase() }}
            </button>
            @if (!bitza.is_root) {
              <button mat-button type="button" (click)="onMove(bitza)">
                <mat-icon>drive_file_move</mat-icon>
                Move
              </button>
              @if (bitza.status === 'active') {
                <button mat-button type="button" (click)="onRetire(bitza)">
                  <mat-icon>archive</mat-icon>
                  Retire
                </button>
              } @else {
                <button mat-button type="button" (click)="onReactivate(bitza)">
                  <mat-icon>unarchive</mat-icon>
                  Reactivate
                </button>
              }
              @if (authService.isAdmin()) {
                <button mat-button color="warn" type="button" (click)="onDelete(bitza)">
                  <mat-icon>delete</mat-icon>
                  Delete
                </button>
              }
            }
          </mat-card-actions>
        </mat-card>
      }

      <div class="filters-row">
        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Type</mat-label>
          <mat-select [value]="filterKind()" (selectionChange)="filterKind.set($event.value)">
            <mat-option value="">All</mat-option>
            <mat-option value="fixed">Fixed</mat-option>
            <mat-option value="mobile">Mobile</mat-option>
            <mat-option value="stock">Stock</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Status</mat-label>
          <mat-select [value]="filterStatus()" (selectionChange)="filterStatus.set($event.value)">
            <mat-option value="">All</mat-option>
            <mat-option value="active">Active</mat-option>
            <mat-option value="retired">Retired</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>Category</mat-label>
          <mat-select
            [value]="filterCategoryId()"
            (selectionChange)="filterCategoryId.set($event.value)"
          >
            <mat-option value="">All</mat-option>
            @for (category of categories(); track category.id) {
              <mat-option [value]="category.id">{{ category.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="filter-field">
          <mat-label>{{ config.teamLabelSingular() }}</mat-label>
          <mat-select [value]="filterTeamId()" (selectionChange)="filterTeamId.set($event.value)">
            <mat-option value="">All</mat-option>
            @for (team of teams(); track team.id) {
              <mat-option [value]="team.id">{{ team.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <button mat-stroked-button type="button" (click)="onManageCategories()">
          <mat-icon>sell</mat-icon>
          Categories
        </button>
      </div>

      @if (childrenLoading()) {
        <div class="loading-row">
          <mat-progress-spinner diameter="28" mode="indeterminate"></mat-progress-spinner>
        </div>
      } @else if (children().length === 0) {
        <p>Nothing here yet.</p>
      } @else {
        <table mat-table [dataSource]="children()" class="children-table">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let child">
              <button class="child-link" type="button" (click)="openBitza(child.id)">
                {{ child.name }}
              </button>
              <span class="bitza-tag">{{ child.kind }}</span>
              @if (child.status === 'retired') {
                <span class="bitza-tag retired-tag">retired</span>
              }
            </td>
          </ng-container>

          <ng-container matColumnDef="stock">
            <th mat-header-cell *matHeaderCellDef>Stock</th>
            <td mat-cell *matCellDef="let child">
              @if (child.kind === 'stock') {
                {{ child.quantity ?? child.fuzzy_state }}
              }
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
        </table>
      }
    }
  `,
  styles: `
    mat-card-title h1 {
      margin: 0;
      font: inherit;
    }

    .breadcrumb {
      margin-bottom: 1rem;
      font-size: 0.9rem;
    }

    .breadcrumb a {
      color: var(--mat-sys-primary);
      text-decoration: none;
    }

    .breadcrumb-sep {
      margin: 0 0.4rem;
      color: var(--mat-sys-on-surface-variant);
    }

    .bitza-card {
      margin-bottom: 1.5rem;
    }

    .retired-tag {
      background: var(--mat-sys-error-container);
      color: var(--mat-sys-on-error-container);
      margin-left: 0.5rem;
    }

    .root-tag {
      background: var(--mat-sys-tertiary-container);
      color: var(--mat-sys-on-tertiary-container);
      margin-right: 0.5rem;
    }

    .action-section {
      margin-top: 1.25rem;
      padding-top: 1rem;
      border-top: 1px solid var(--mat-sys-outline-variant);
    }

    .filters-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }

    .filter-field {
      width: 160px;
    }

    .children-table {
      width: 100%;
    }

    .child-link {
      background: none;
      border: none;
      padding: 0;
      color: var(--mat-sys-primary);
      font: inherit;
      cursor: pointer;
      text-decoration: underline;
    }

    .loading-row {
      display: flex;
      justify-content: center;
      padding: 2rem 0;
    }

    .error-text {
      color: var(--mat-sys-error);
    }
  `,
})
export class BitzaBrowser {
  protected readonly config = inject(AppConfigService);
  protected readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly bitzaService = inject(BitzaService);
  private readonly teamService = inject(TeamService);
  private readonly categoryService = inject(CategoryService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly columns = ['name', 'stock'];

  protected readonly currentId = toSignal(
    this.route.paramMap.pipe(map((params) => params.get('id'))),
    { initialValue: null },
  );

  private readonly currentId$ = toObservable(this.currentId);

  private readonly reload = signal(0);
  private readonly reload$ = toObservable(this.reload);

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  protected readonly filterKind = signal<BitzaKind | ''>('');
  protected readonly filterStatus = signal<BitzaStatus | ''>('');
  protected readonly filterCategoryId = signal('');
  protected readonly filterTeamId = signal('');

  private readonly filtersBundle = computed(() => ({
    kind: this.filterKind() || undefined,
    status: this.filterStatus() || undefined,
    category_id: this.filterCategoryId() || undefined,
    responsible_team_id: this.filterTeamId() || undefined,
  }));
  private readonly filtersBundle$ = toObservable(this.filtersBundle);

  protected readonly teams = toSignal(
    this.teamService.list().pipe(catchError(() => of<TeamListItem[]>([]))),
    { initialValue: [] },
  );

  private readonly categoriesReload = signal(0);
  protected readonly categories = toSignal(
    toObservable(this.categoriesReload).pipe(
      switchMap(() => this.categoryService.list().pipe(catchError(() => of<Category[]>([])))),
    ),
    { initialValue: [] },
  );

  private readonly pageData = toSignal(
    combineLatest([this.currentId$, this.reload$]).pipe(
      switchMap(([id]) => {
        if (!id) {
          return of({ bitza: null as Bitza | null, breadcrumb: [] as BitzaAncestor[] });
        }
        return this.bitzaService.get(id).pipe(
          switchMap((bitza) =>
            this.bitzaService
              .getAncestors(id)
              // Nearest parent first, root last (see BitzaAncestor) —
              // reversed here for root-first breadcrumb display.
              .pipe(map((ancestors) => ({ bitza, breadcrumb: [...ancestors].reverse() }))),
          ),
          catchError(() => {
            this.loadErrorSignal.set(true);
            return of({ bitza: null as Bitza | null, breadcrumb: [] as BitzaAncestor[] });
          }),
        );
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly currentBitza = computed(() => this.pageData()?.bitza ?? null);
  /**
   * Ancestors only, root first — excludes the current bitza itself (the
   * ancestors endpoint never includes it, so no slicing needed here).
   * Previously rebuilt via N sequential GET /bitzas/{id} calls walking
   * parent_id one hop at a time (RxJS `expand`); now one call to
   * GET /bitzas/{id}/ancestors. See bitza_schema_reconciliation_todo.md.
   */
  protected readonly breadcrumb = computed(() => this.pageData()?.breadcrumb ?? []);

  private readonly childrenResult = toSignal(
    combineLatest([this.currentId$, this.reload$, this.filtersBundle$]).pipe(
      switchMap(([id, , filters]) => {
        const params: BitzaListParams = { ...filters };
        if (id) {
          params.parent_id = id;
        } else {
          params.root_only = true;
        }
        return this.bitzaService.list(params).pipe(catchError(() => of<BitzaListItem[]>([])));
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly childrenLoading = computed(() => this.childrenResult() === undefined);
  protected readonly children = computed(() => this.childrenResult() ?? []);

  protected openBitza(id: string): void {
    this.router.navigate(['/bitzas', id]);
  }

  protected onCreateChild(parent: Bitza): void {
    const data: BitzaFormDialogData = {
      parentId: parent.id,
      defaultTeamId: parent.responsible_team_id,
    };
    const dialogRef = this.dialog.open(BitzaFormDialog, { width: '520px', data });
    dialogRef.afterClosed().subscribe((result?: BitzaFormResult) => {
      if (!result || result.mode !== 'create') {
        return;
      }
      this.bitzaService.create(result.value).subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onEdit(bitza: Bitza): void {
    const dialogRef = this.dialog.open(BitzaFormDialog, {
      width: '520px',
      data: { bitza } satisfies BitzaFormDialogData,
    });
    dialogRef.afterClosed().subscribe((result?: BitzaFormResult) => {
      if (!result || result.mode !== 'edit') {
        return;
      }
      this.bitzaService
        .update(bitza.id, result.value)
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onMove(bitza: Bitza): void {
    const data: MoveBitzaDialogData = { bitza };
    const dialogRef = this.dialog.open(MoveBitzaDialog, { width: '480px', data });
    dialogRef.afterClosed().subscribe((result?: MoveBitzaResult) => {
      if (!result) {
        return;
      }
      this.bitzaService.update(bitza.id, { parent_id: result.newParentId }).subscribe({
        next: () => this.reload.update((n) => n + 1),
        error: (err: HttpErrorResponse) => {
          const message =
            err.status === 409
              ? "Can't move it there — that would nest it inside itself."
              : 'Something went wrong moving this bitza.';
          this.snackBar.open(message, 'Dismiss', { duration: 6000 });
        },
      });
    });
  }

  protected onRetire(bitza: Bitza): void {
    const dialogRef = this.dialog.open(RetireDialog, { width: '420px' });
    dialogRef.afterClosed().subscribe((result?: RetireDialogResult) => {
      if (!result) {
        return;
      }
      this.bitzaService.retire(bitza.id, result).subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onReactivate(bitza: Bitza): void {
    const data: ConfirmDialogData = {
      title: 'Reactivate this bitza?',
      message: `${bitza.name} will show as active again.`,
      confirmLabel: 'Reactivate',
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '400px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.bitzaService.reactivate(bitza.id).subscribe(() => this.reload.update((n) => n + 1));
    });
  }

  protected onReassignTeam(bitza: Bitza): void {
    const data: ReassignTeamDialogData = {
      kind: bitza.kind,
      currentTeamId: bitza.responsible_team_id,
    };
    const dialogRef = this.dialog.open(ReassignTeamDialog, { width: '480px', data });
    dialogRef.afterClosed().subscribe((result?: ReassignTeamResult) => {
      if (!result) {
        return;
      }
      this.bitzaService
        .reassignTeam(bitza.id, { team_id: result.teamId, cascade_scope: result.cascadeScope })
        .subscribe((response) => {
          this.reload.update((n) => n + 1);
          const count = response.updated_count;
          this.snackBar.open(
            `Reassigned ${count} ${count === 1 ? 'bitza' : 'bitzas'}.`,
            'Dismiss',
            { duration: 4000 },
          );
        });
    });
  }

  protected onDelete(bitza: Bitza): void {
    const data: ConfirmDialogData = {
      title: `Delete ${bitza.name}?`,
      message: "This can't be undone. It will fail if this bitza still has children.",
      confirmLabel: 'Delete',
      destructive: true,
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '420px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.bitzaService.delete(bitza.id).subscribe({
        next: () => {
          const parentId = bitza.parent_id;
          this.router.navigate(parentId ? ['/bitzas', parentId] : ['/bitzas']);
        },
        error: (err: HttpErrorResponse) => {
          const message =
            err.status === 409
              ? "Can't delete — this bitza still has children."
              : 'Something went wrong deleting this bitza.';
          this.snackBar.open(message, 'Dismiss', { duration: 6000 });
        },
      });
    });
  }

  protected onManageCategories(): void {
    const dialogRef = this.dialog.open(CategoryManagerDialog, { width: '480px' });
    dialogRef.afterClosed().subscribe(() => this.categoriesReload.update((n) => n + 1));
  }

  /** Stock adjustments change bitza.quantity, which the detail card and children table both show. */
  protected onStockAdjusted(): void {
    this.reload.update((n) => n + 1);
  }

  protected onViewLabel(bitza: Bitza): void {
    const data: BitzaLabelDialogData = { bitza };
    this.dialog.open(BitzaLabelDialog, { width: '360px', data });
  }
}
