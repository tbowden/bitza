import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ImageService } from './image.service';

describe('ImageService', () => {
  let service: ImageService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ImageService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('uploads a file as multipart form data', async () => {
    const file = new File(['abc'], 'photo.png', { type: 'image/png' });
    const promise = firstValueFrom(service.upload('b1', file, true));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/images`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body instanceof FormData).toBe(true);
    const body = req.request.body as FormData;
    expect(body.get('file')).toBe(file);
    expect(body.get('is_primary')).toBe('true');
    req.flush({
      id: 'i1',
      bitza_id: 'b1',
      is_primary: true,
      filename: 'photo.png',
      created_at: '2026-01-01',
    });
    await promise;
  });

  it('requests the image file as a blob', async () => {
    const promise = firstValueFrom(service.getBlob('b1', 'i1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/images/i1`);
    expect(req.request.responseType).toBe('blob');
    req.flush(new Blob(['data'], { type: 'image/png' }));
    await promise;
  });

  it('always sets is_primary true when setting a cover photo', async () => {
    const promise = firstValueFrom(service.setPrimary('b1', 'i1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/images/i1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ is_primary: true });
    req.flush({
      id: 'i1',
      bitza_id: 'b1',
      is_primary: true,
      filename: 'photo.png',
      created_at: '2026-01-01',
    });
    await promise;
  });

  it('deletes an image', async () => {
    const promise = firstValueFrom(service.delete('b1', 'i1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/images/i1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
    await promise;
  });
});
