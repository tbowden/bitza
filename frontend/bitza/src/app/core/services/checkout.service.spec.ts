import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CheckoutService } from './checkout.service';

describe('CheckoutService', () => {
  let service: CheckoutService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CheckoutService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('checks out with the given request body', async () => {
    const promise = firstValueFrom(service.checkout('b1', { note: 'for the comp' }));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/checkout`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ note: 'for the comp' });
    req.flush({
      id: 'c1',
      bitza_id: 'b1',
      user_id: 'u1',
      team_context: null,
      note: 'for the comp',
      checked_out_at: '2026-01-01T00:00:00Z',
      checked_in_at: null,
    });
    await promise;
  });

  it('checks in with an optional note', async () => {
    const promise = firstValueFrom(service.checkin('b1', {}));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/checkin`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush({
      id: 'c1',
      bitza_id: 'b1',
      user_id: 'u1',
      team_context: null,
      note: null,
      checked_out_at: '2026-01-01T00:00:00Z',
      checked_in_at: '2026-01-02T00:00:00Z',
    });
    await promise;
  });

  it('fetches checkout history', async () => {
    const promise = firstValueFrom(service.history('b1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/checkouts`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
    await promise;
  });
});
