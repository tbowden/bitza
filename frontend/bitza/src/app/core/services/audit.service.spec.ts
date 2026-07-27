import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuditService } from './audit.service';

describe('AuditService', () => {
  let service: AuditService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuditService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists with no params by default', async () => {
    const promise = firstValueFrom(service.list());
    const req = httpMock.expectOne(`${environment.apiUrl}/audit/`);
    expect(req.request.params.keys().length).toBe(0);
    req.flush([]);
    await promise;
  });

  it('filters by entity_type and entity_id when provided', async () => {
    const promise = firstValueFrom(service.list({ entity_type: 'bitza', entity_id: 'b1' }));
    const req = httpMock.expectOne(
      (r) =>
        r.url === `${environment.apiUrl}/audit/` &&
        r.params.get('entity_type') === 'bitza' &&
        r.params.get('entity_id') === 'b1',
    );
    req.flush([]);
    await promise;
  });
});
