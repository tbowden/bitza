import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { catchError, of } from 'rxjs';
import { AuditService } from '../../../core/services/audit.service';
import { UserService } from '../../../core/services/user.service';
import { AuditLogEntry, User } from '../../../core/models';

@Component({
  selector: 'app-audit-log',
  imports: [
    DatePipe,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatTableModule,
  ],
  templateUrl: './audit-log.html',
  styleUrl: './audit-log.scss',
})
export class AuditLog {
  private readonly auditService = inject(AuditService);
  private readonly userService = inject(UserService);

  protected readonly columns = ['created_at', 'user', 'action', 'entity', 'description'];

  protected readonly filterUserId = signal('');
  protected readonly filterAction = signal('');

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  protected readonly users = toSignal(
    this.userService.list().pipe(catchError(() => of<User[]>([]))),
    { initialValue: [] },
  );

  /**
   * GET /audit/ only supports entity_type/entity_id/limit server-side
   * (see AuditListParams) — fetched once, unfiltered by user/action.
   */
  private readonly entriesResult = toSignal(
    this.auditService.list().pipe(
      catchError(() => {
        this.loadErrorSignal.set(true);
        return of<AuditLogEntry[]>([]);
      }),
    ),
    { initialValue: undefined },
  );

  protected readonly loading = computed(() => this.entriesResult() === undefined);
  private readonly entries = computed(() => this.entriesResult() ?? []);

  /** User/action filtering happens here, client-side, against the fetched page. */
  protected readonly rows = computed(() => {
    const userId = this.filterUserId();
    const action = this.filterAction().trim().toLowerCase();
    return this.entries().filter((entry) => {
      if (userId && entry.user_id !== userId) {
        return false;
      }
      if (action && !entry.action.toLowerCase().includes(action)) {
        return false;
      }
      return true;
    });
  });

  protected onUserFilterChange(value: string): void {
    this.filterUserId.set(value);
  }

  protected onActionFilterInput(event: Event): void {
    this.filterAction.set((event.target as HTMLInputElement).value);
  }
}
