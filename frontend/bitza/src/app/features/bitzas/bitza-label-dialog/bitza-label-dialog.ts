import { Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { toDataURL } from 'qrcode';
import { Bitza } from '../../../core/models';

export interface BitzaLabelDialogData {
  bitza: Bitza;
}

/**
 * Deliberately its own dialog rather than inline content on the bitza
 * page: viewing/printing a label is an occasional, one-shot action (like
 * Edit or Move), not information about the bitza worth showing by
 * default — see the "QR code presentation" discussion. The QR is
 * generated lazily, only when this dialog actually opens, rather than
 * eagerly on every bitza page visit.
 */
@Component({
  selector: 'app-bitza-label-dialog',
  imports: [MatButtonModule, MatDialogModule, MatIconModule, MatProgressSpinnerModule],
  templateUrl: './bitza-label-dialog.html',
  styleUrl: './bitza-label-dialog.scss',
})
export class BitzaLabelDialog {
  protected readonly dialogRef = inject(MatDialogRef<BitzaLabelDialog>);
  protected readonly data = inject<BitzaLabelDialogData>(MAT_DIALOG_DATA);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly qrDataUrl = signal<string | null>(null);

  constructor() {
    const url = `${window.location.origin}/bitza/${this.data.bitza.id}/`;
    toDataURL(url, { margin: 1, width: 220 })
      .then((dataUrl) => this.qrDataUrl.set(dataUrl))
      .catch(() => {
        this.snackBar.open("Couldn't generate the QR code.", 'Dismiss', { duration: 5000 });
      });
  }

  /**
   * Prints via a small dedicated popup window containing only the label,
   * rather than window.print() + CSS rules trying to hide everything
   * else on the page (fragile even before this was a dialog, and would
   * only get worse fighting the app-shell/overlay boundary). Safe
   * against HTML injection — built via DOM APIs / property assignment,
   * never string-concatenated into markup.
   */
  protected onPrint(): void {
    const qr = this.qrDataUrl();
    if (!qr) {
      return;
    }
    const printWindow = window.open('', '_blank', 'width=400,height=520');
    if (!printWindow) {
      this.snackBar.open(
        "Couldn't open the print window — check your browser's popup settings.",
        'Dismiss',
        { duration: 6000 },
      );
      return;
    }

    const doc = printWindow.document;
    doc.title = `${this.data.bitza.name} — label`;

    const style = doc.createElement('style');
    style.textContent = `
      body {
        margin: 0;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-family: sans-serif;
      }
      img { width: 220px; height: 220px; }
      p { margin-top: 12px; font-size: 14px; }
    `;
    doc.head.appendChild(style);

    const img = doc.createElement('img');
    img.src = qr;
    img.alt = '';
    doc.body.appendChild(img);

    const caption = doc.createElement('p');
    caption.textContent = this.data.bitza.name;
    doc.body.appendChild(caption);

    printWindow.focus();
    printWindow.print();
  }
}
