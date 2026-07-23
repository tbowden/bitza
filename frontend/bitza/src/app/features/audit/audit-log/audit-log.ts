import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { catchError, forkJoin, map, of, switchMap } from 'rxjs';
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

  protected readonly columns = ['created_at', 'user', 'action', 'summary'];

  protected readonly filterUserId = signal('');
  protected readonly filterAction = signal('');

  private readonly loadErrorSignal = signal(false);
  protected readonly loadError = this.loadErrorSignal.asReadonly();

  protected readonly users = toSignal(
    this.userService.list().pipe(catchError(() => of<User[]>([]))),
    { initialValue: [] },
  );

  private readonly filtersBundle = computed(() => ({
    user_id: this.filterUserId() || undefined,
    action: this.filterAction().trim() || undefined,
  }));
  private readonly filtersBundle$ = toObservable(this.filtersBundle);

  private readonly entriesResult = toSignal(
    this.filtersBundle$.pipe(
      switchMap((filters) =>
        this.auditService.list(filters).pipe(
          catchError(() => {
            this.loadErrorSignal.set(true);
            return of<AuditLogEntry[]>([]);
          }),
        ),
      ),
    ),
    { initialValue: undefined },
  );

  protected readonly loading = computed(() => this.entriesResult() === undefined);
  private readonly entries = computed(() => this.entriesResult() ?? []);

  private readonly userNames = toSignal(
    toObservable(this.entries).pipe(
      switchMap((entries) => {
        const ids = [...new Set(entries.map((entry) => entry.user_id))];
        if (ids.length === 0) {
          return of(new Map<string, string>());
        }
        return forkJoin(
          ids.map((id) => this.userService.get(id).pipe(catchError(() => of(null)))),
        ).pipe(
          map(
            (users) =>
              new Map(
                users
                  .filter((user): user is NonNullable<typeof user> => user !== null)
                  .map((user) => [user.id, user.username]),
              ),
          ),
        );
      }),
    ),
    { initialValue: new Map<string, string>() },
  );

  protected readonly rows = computed(() =>
    this.entries().map((entry) => ({
      ...entry,
      username: this.userNames().get(entry.user_id) ?? entry.user_id,
    })),
  );

  protected onUserFilterChange(value: string): void {
    this.filterUserId.set(value);
  }

  protected onActionFilterInput(event: Event): void {
    this.filterAction.set((event.target as HTMLInputElement).value);
  }
}
