import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { BitzaService } from './bitza.service';

describe('BitzaService', () => {
  let service: BitzaService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(BitzaService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('requests direct children only, never a recursive fetch, when parent_id is given', async () => {
    const promise = firstValueFrom(service.list({ parent_id: 'p1' }));
    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/bitzas/` && r.params.get('parent_id') === 'p1',
    );
    expect(req.request.params.keys().length).toBe(1);
    req.flush([]);
    await promise;
  });

  it('requests root_only when browsing the top level', async () => {
    const promise = firstValueFrom(service.list({ root_only: true }));
    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/bitzas/` && r.params.get('root_only') === 'true',
    );
    req.flush([]);
    await promise;
  });

  it('omits undefined filter values instead of sending empty params', async () => {
    const promise = firstValueFrom(service.list({ kind: 'stock', status: undefined }));
    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/bitzas/` && r.params.get('kind') === 'stock',
    );
    expect(req.request.params.keys()).toEqual(['kind']);
    req.flush([]);
    await promise;
  });

  it('retires a bitza with reason and note', async () => {
    const promise = firstValueFrom(service.retire('b1', { reason: 'lost', note: 'gone' }));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/retire`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ reason: 'lost', note: 'gone' });
    req.flush({});
    await promise;
  });

  it('reassigns team with the required cascade_scope', async () => {
    const promise = firstValueFrom(
      service.reassignTeam('b1', { team_id: 't2', cascade_scope: 'all_descendants' }),
    );
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1/reassign-team`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ team_id: 't2', cascade_scope: 'all_descendants' });
    req.flush(null);
    await promise;
  });

  it('hard-deletes via DELETE', async () => {
    const promise = firstValueFrom(service.delete('b1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/bitzas/b1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
    await promise;
  });
});
