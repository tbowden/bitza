import { Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { catchError, forkJoin, map, of, switchMap } from 'rxjs';
import { ImageService } from '../../../core/services/image.service';
import { BitzaImage } from '../../../core/models';
import { ConfirmDialog, ConfirmDialogData } from '../../../shared/confirm-dialog/confirm-dialog';

interface ImageUrl {
  id: string;
  url: string;
  isPrimary: boolean;
}

@Component({
  selector: 'app-image-gallery',
  imports: [MatButtonModule, MatIconModule, MatProgressSpinnerModule, MatTooltipModule],
  template: `
    <div class="gallery-header">
      <h3>Images</h3>
      <label class="upload-button">
        <input
          type="file"
          accept="image/*"
          class="visually-hidden"
          (change)="onFileSelected($event)"
        />
        <span mat-stroked-button role="button">
          <mat-icon>upload</mat-icon>
          Upload
        </span>
      </label>
    </div>

    @if (loading()) {
      <mat-progress-spinner diameter="24" mode="indeterminate"></mat-progress-spinner>
    } @else if (imageUrls().length === 0) {
      <p>No images yet.</p>
    } @else {
      <div class="image-grid">
        @for (image of imageUrls(); track image.id) {
          <div class="image-tile">
            <img [src]="image.url" alt="" width="120" height="120" />
            @if (image.isPrimary) {
              <span class="primary-badge">Cover</span>
            }
            <div class="tile-actions">
              @if (!image.isPrimary) {
                <button
                  mat-icon-button
                  type="button"
                  matTooltip="Set as cover photo"
                  aria-label="Set as cover photo"
                  (click)="onSetPrimary(image.id)"
                >
                  <mat-icon>star_border</mat-icon>
                </button>
              }
              <button
                mat-icon-button
                type="button"
                matTooltip="Delete image"
                aria-label="Delete image"
                (click)="onDelete(image.id)"
              >
                <mat-icon>delete</mat-icon>
              </button>
            </div>
          </div>
        }
      </div>
    }
  `,
  styles: `
    .gallery-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.5rem;
    }

    .gallery-header h3 {
      margin: 0;
    }

    .upload-button {
      cursor: pointer;
    }

    .visually-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }

    .image-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
    }

    .image-tile {
      position: relative;
      width: 120px;
    }

    .image-tile img {
      display: block;
      border-radius: 4px;
      object-fit: cover;
    }

    .primary-badge {
      position: absolute;
      top: 4px;
      left: 4px;
      background: var(--mat-sys-primary);
      color: var(--mat-sys-on-primary);
      font-size: 0.6875rem;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
    }

    .tile-actions {
      display: flex;
      justify-content: center;
    }
  `,
})
export class ImageGallery {
  readonly bitzaId = input.required<string>();

  private readonly imageService = inject(ImageService);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  private readonly reload = signal(0);
  private readonly bitzaId$ = toObservable(this.bitzaId);
  private readonly reload$ = toObservable(this.reload);

  private readonly metadataResult = toSignal(
    this.reload$.pipe(
      switchMap(() => this.bitzaId$),
      switchMap((id) => this.imageService.list(id).pipe(catchError(() => of<BitzaImage[]>([])))),
    ),
    { initialValue: undefined },
  );

  protected readonly loading = computed(() => this.metadataResult() === undefined);
  private readonly metadata = computed(() => this.metadataResult() ?? []);

  protected readonly imageUrls = signal<ImageUrl[]>([]);
  private previousObjectUrls: string[] = [];

  constructor() {
    toObservable(this.metadata)
      .pipe(
        switchMap((images) => {
          if (images.length === 0) {
            return of([] as ImageUrl[]);
          }
          return forkJoin(
            images.map((image) =>
              this.imageService.getBlob(this.bitzaId(), image.id).pipe(
                map((blob) => ({
                  id: image.id,
                  url: URL.createObjectURL(blob),
                  isPrimary: image.is_primary,
                })),
                catchError(() => of(null)),
              ),
            ),
          ).pipe(map((results) => results.filter((r): r is ImageUrl => r !== null)));
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((urls) => {
        for (const url of this.previousObjectUrls) {
          URL.revokeObjectURL(url);
        }
        this.previousObjectUrls = urls.map((entry) => entry.url);
        this.imageUrls.set(urls);
      });

    this.destroyRef.onDestroy(() => {
      for (const url of this.previousObjectUrls) {
        URL.revokeObjectURL(url);
      }
    });
  }

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) {
      return;
    }
    this.imageService.upload(this.bitzaId(), file).subscribe({
      next: () => this.reload.update((n) => n + 1),
      error: () => this.snackBar.open('Upload failed.', 'Dismiss', { duration: 5000 }),
    });
  }

  protected onSetPrimary(imageId: string): void {
    this.imageService
      .setPrimary(this.bitzaId(), imageId)
      .subscribe(() => this.reload.update((n) => n + 1));
  }

  protected onDelete(imageId: string): void {
    const data: ConfirmDialogData = {
      title: 'Delete image?',
      message: "This can't be undone.",
      confirmLabel: 'Delete',
      destructive: true,
    };
    const dialogRef = this.dialog.open(ConfirmDialog, { width: '400px', data });
    dialogRef.afterClosed().subscribe((confirmed?: boolean) => {
      if (!confirmed) {
        return;
      }
      this.imageService
        .delete(this.bitzaId(), imageId)
        .subscribe(() => this.reload.update((n) => n + 1));
    });
  }
}
