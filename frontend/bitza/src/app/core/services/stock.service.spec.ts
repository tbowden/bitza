import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { StockService } from './stock.service';

describe('StockService', () => {
  let service: StockService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(StockService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('posts a positive delta for stock in', async () => {
    const promise = firstValueFrom(service.adjust('b1', { delta: 10, note: 'restock' }));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/stock-adjustments`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ delta: 10, note: 'restock' });
    req.flush({
      id: 's1',
      bitza_id: 'b1',
      delta: 10,
      note: 'restock',
      user_id: 'u1',
      created_at: '2026-01-01',
    });
    await promise;
  });

  it('posts a negative delta for stock out', async () => {
    const promise = firstValueFrom(service.adjust('b1', { delta: -3 }));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/stock-adjustments`);
    expect(req.request.body).toEqual({ delta: -3 });
    req.flush({
      id: 's2',
      bitza_id: 'b1',
      delta: -3,
      note: null,
      user_id: 'u1',
      created_at: '2026-01-01',
    });
    await promise;
  });

  it('fetches stock adjustment history', async () => {
    const promise = firstValueFrom(service.history('b1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/stock-adjustments`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
    await promise;
  });
});
