import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ProjectService } from './project.service';

describe('ProjectService', () => {
  let service: ProjectService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ProjectService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lists all projects with no params', async () => {
    const promise = firstValueFrom(service.list());
    const req = httpMock.expectOne(`${environment.apiUrl}/projects/`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().length).toBe(0);
    req.flush([{ id: 't1', name: 'Aero', member_count: 3 }]);
    const result = await promise;
    expect(result[0].name).toBe('Aero');
  });

  it('filters projects by user_id when provided', async () => {
    const promise = firstValueFrom(service.list('u1'));
    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/projects/` && r.params.get('user_id') === 'u1',
    );
    req.flush([]);
    await promise;
  });

  it('creates a project', async () => {
    const promise = firstValueFrom(service.create({ name: 'Battery', description: 'cells' }));
    const req = httpMock.expectOne(`${environment.apiUrl}/projects/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'Battery', description: 'cells' });
    req.flush({
      id: 't2',
      name: 'Battery',
      description: 'cells',
      member_count: 0,
      created_at: '2026-01-01',
    });
    await promise;
  });

  it('deletes a project', async () => {
    const promise = firstValueFrom(service.delete('t1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/projects/t1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
    await promise;
  });

  it('adds a member with the documented payload shape', async () => {
    const promise = firstValueFrom(service.addMember('t1', { user_id: 'u1', is_primary: true }));
    const req = httpMock.expectOne(`${environment.apiUrl}/projects/t1/members`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ user_id: 'u1', is_primary: true });
    req.flush({
      id: 'm1',
      user_id: 'u1',
      project_id: 't1',
      is_primary: true,
      user_display_name: 'Sam Smith',
    });
    await promise;
  });

  it('sets primary via PATCH on the membership', async () => {
    const promise = firstValueFrom(service.setPrimary('t1', 'u1', false));
    const req = httpMock.expectOne(`${environment.apiUrl}/projects/t1/members/u1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ is_primary: false });
    req.flush({
      id: 'm1',
      user_id: 'u1',
      project_id: 't1',
      is_primary: false,
      user_display_name: 'Sam Smith',
    });
    await promise;
  });

  it('removes a member', async () => {
    const promise = firstValueFrom(service.removeMember('t1', 'u1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/projects/t1/members/u1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
    await promise;
  });

  it("fetches the current user's own memberships, including is_primary", async () => {
    const promise = firstValueFrom(service.listMine());
    const req = httpMock.expectOne(`${environment.apiUrl}/projects/mine`);
    expect(req.request.method).toBe('GET');
    req.flush([{ project_id: 't1', project_name: 'Aero', is_primary: true }]);
    const result = await promise;
    expect(result[0]).toEqual({ project_id: 't1', project_name: 'Aero', is_primary: true });
  });
});
