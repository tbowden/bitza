import { HttpClient } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { BitzaImage } from '../models';

/**
 * There's no unauthenticated static path for image files — a plain
 * `<img src>` won't send the Authorization header, so every file fetch
 * here goes through HttpClient with `responseType: 'blob'` and the
 * caller builds an object URL from the result. See "Images" in
 * bitza_project_context.md.
 */
@Service()
export class ImageService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/bitzas`;

  list(bitzaId: string): Observable<BitzaImage[]> {
    return this.http.get<BitzaImage[]>(`${this.baseUrl}/${bitzaId}/images`);
  }

  /** The first image ever uploaded for a bitza is always made primary, regardless of isPrimary. */
  upload(bitzaId: string, file: File, isPrimary?: boolean): Observable<BitzaImage> {
    const formData = new FormData();
    formData.append('file', file);
    if (isPrimary !== undefined) {
      formData.append('is_primary', String(isPrimary));
    }
    return this.http.post<BitzaImage>(`${this.baseUrl}/${bitzaId}/images`, formData);
  }

  getBlob(bitzaId: string, imageId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/${bitzaId}/images/${imageId}`, { responseType: 'blob' });
  }

  setPrimary(bitzaId: string, imageId: string): Observable<BitzaImage> {
    return this.http.patch<BitzaImage>(`${this.baseUrl}/${bitzaId}/images/${imageId}`, {
      is_primary: true,
    });
  }

  /** If this was the primary image, the backend promotes the oldest remaining one. */
  delete(bitzaId: string, imageId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${bitzaId}/images/${imageId}`);
  }
}
