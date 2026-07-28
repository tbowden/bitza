import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { catchError, of, switchMap } from 'rxjs';
import { BitzaService } from '../../../core/services/bitza.service';
import { Bitza, BitzaListItem } from '../../../core/models';

export interface MoveBitzaDialogData {
  bitza: Bitza;
}

export interface MoveBitzaResult {
  newParentId: string;
}

interface Crumb {
  id: string;
  name: string;
}

@Component({
  selector: 'app-move-bitza-dialog',
  imports: [
    MatButtonModule,
    MatDialogModule,
    MatIconModule,
    MatListModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>Move "{{ data.bitza.name }}"</h2>

    <mat-dialog-content>
      <nav class="crumb-trail" aria-label="Browse location">
        @for (crumb of pathStack(); track crumb.id; let i = $index) {
          @if (i > 0) {
            <span class="crumb-sep">/</span>
          }
          <button class="crumb-link" type="button" (click)="jumpTo(i)">{{ crumb.name }}</button>
        }
      </nav>

      <button
        mat-flat-button
        color="primary"
        type="button"
        class="move-here-button"
        [disabled]="currentLocationId() === data.bitza.id"
        (click)="onMoveHere()"
      >
        <mat-icon>drive_file_move</mat-icon>
        Move here — into "{{ currentLocationName() }}"
      </button>

      @if (loading()) {
        <div class="loading-row">
          <mat-progress-spinner diameter="24" mode="indeterminate"></mat-progress-spinner>
        </div>
      } @else if (children().length === 0) {
        <p>Nothing else nested here.</p>
      } @else {
        <mat-nav-list>
          @for (child of children(); track child.id) {
            <a
              mat-list-item
              [class.disabled-item]="child.id === data.bitza.id"
              (click)="child.id !== data.bitza.id && drillInto(child)"
            >
              <span matListItemTitle>{{ child.name }}</span>
              @if (child.id === data.bitza.id) {
                <span matListItemLine>the bitza being moved</span>
              }
            </a>
          }
        </mat-nav-list>
      }
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="dialogRef.close()">Cancel</button>
    </mat-dialog-actions>
  `,
  styles: `
    .crumb-trail {
      margin-bottom: 1rem;
      font-size: 0.9rem;
    }

    .crumb-link {
      background: none;
      border: none;
      padding: 0;
      color: var(--mat-sys-primary);
      font: inherit;
      cursor: pointer;
      text-decoration: underline;
    }

    .crumb-sep {
      margin: 0 0.4rem;
      color: var(--mat-sys-on-surface-variant);
    }

    .move-here-button {
      width: 100%;
      margin-bottom: 1rem;
    }

    .disabled-item {
      opacity: 0.5;
      pointer-events: none;
    }

    .loading-row {
      display: flex;
      justify-content: center;
      padding: 1.5rem 0;
    }
  `,
})
export class MoveBitzaDialog {
  protected readonly dialogRef = inject(MatDialogRef<MoveBitzaDialog, MoveBitzaResult>);
  protected readonly data = inject<MoveBitzaDialogData>(MAT_DIALOG_DATA);
  private readonly bitzaService = inject(BitzaService);

  /** Breadcrumb from the tree root down to wherever we're currently browsing. */
  protected readonly pathStack = signal<Crumb[]>([]);

  protected readonly currentLocationId = computed(() => {
    const stack = this.pathStack();
    return stack.length > 0 ? stack[stack.length - 1].id : null;
  });

  protected readonly currentLocationName = computed(() => {
    const stack = this.pathStack();
    return stack.length > 0 ? stack[stack.length - 1].name : '…';
  });

  private readonly currentLocationId$ = toObservable(this.currentLocationId);

  private readonly childrenResult = toSignal(
    this.currentLocationId$.pipe(
      switchMap((id) => {
        if (!id) {
          return of(undefined);
        }
        return this.bitzaService
          .list({ parent_id: id })
          .pipe(catchError(() => of<BitzaListItem[]>([])));
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly loading = computed(() => this.childrenResult() === undefined);
  protected readonly children = computed(() => this.childrenResult() ?? []);

  constructor() {
    // Seed the picker at the tree root.
    this.bitzaService
      .list({ root_only: true })
      .pipe(catchError(() => of<BitzaListItem[]>([])))
      .subscribe((roots) => {
        if (roots.length > 0) {
          this.pathStack.set([{ id: roots[0].id, name: roots[0].name }]);
        }
      });
  }

  protected drillInto(child: BitzaListItem): void {
    this.pathStack.update((stack) => [...stack, { id: child.id, name: child.name }]);
  }

  protected jumpTo(index: number): void {
    this.pathStack.update((stack) => stack.slice(0, index + 1));
  }

  protected onMoveHere(): void {
    const newParentId = this.currentLocationId();
    if (!newParentId || newParentId === this.data.bitza.id) {
      return;
    }
    this.dialogRef.close({ newParentId });
  }
}
