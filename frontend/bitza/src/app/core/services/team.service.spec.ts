import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { TeamService } from './team.service';

describe('TeamService', () => {
  let service: TeamService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(TeamService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists all teams with no params', async () => {
    const promise = firstValueFrom(service.list());
    const req = httpMock.expectOne(`${environment.apiUrl}/teams/`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().length).toBe(0);
    req.flush([{ id: 't1', name: 'Aero', description: null, created_at: '2026-01-01' }]);
    const result = await promise;
    expect(result[0].name).toBe('Aero');
  });

  it('filters teams by user_id when provided', async () => {
    const promise = firstValueFrom(service.list('u1'));
    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/teams/` && r.params.get('user_id') === 'u1',
    );
    req.flush([]);
    await promise;
  });

  it('creates a team', async () => {
    const promise = firstValueFrom(service.create({ name: 'Battery', description: 'cells' }));
    const req = httpMock.expectOne(`${environment.apiUrl}/teams/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'Battery', description: 'cells' });
    req.flush({ id: 't2', name: 'Battery', description: 'cells', created_at: '2026-01-01' });
    await promise;
  });

  it('deletes a team', async () => {
    const promise = firstValueFrom(service.delete('t1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/teams/t1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
    await promise;
  });

  it('adds a member with the documented payload shape', async () => {
    const promise = firstValueFrom(service.addMember('t1', { user_id: 'u1', is_primary: true }));
    const req = httpMock.expectOne(`${environment.apiUrl}/teams/t1/members`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_id: 'u1', is_primary: true });
    req.flush({ user_id: 'u1', team_id: 't1', is_primary: true });
    await promise;
  });

  it('sets primary via PATCH on the membership', async () => {
    const promise = firstValueFrom(service.setPrimary('t1', 'u1', false));
    const req = httpMock.expectOne(`${environment.apiUrl}/teams/t1/members/u1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ is_primary: false });
    req.flush({ user_id: 'u1', team_id: 't1', is_primary: false });
    await promise;
  });

  it('removes a member', async () => {
    const promise = firstValueFrom(service.removeMember('t1', 'u1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/teams/t1/members/u1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
    await promise;
  });
});
