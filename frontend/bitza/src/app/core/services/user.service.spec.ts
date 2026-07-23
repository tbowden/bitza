import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { UserService } from './user.service';

describe('UserService', () => {
  let service: UserService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(UserService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('creates a user with the given role', async () => {
    const promise = firstValueFrom(
      service.create({ email: 'a@b.com', username: 'sam', password: 'hunter2', role: 'user' }),
    );
    const req = httpMock.expectOne(`${environment.apiUrl}/users/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      email: 'a@b.com',
      username: 'sam',
      password: 'hunter2',
      role: 'user',
    });
    req.flush({
      id: 'u1',
      email: 'a@b.com',
      username: 'sam',
      role: 'user',
      is_suspended: false,
      created_at: '2026-01-01',
    });
    await promise;
  });

  it('sends only the provided fields on admin update', async () => {
    const promise = firstValueFrom(service.adminUpdate('u1', { is_suspended: true }));
    const req = httpMock.expectOne(`${environment.apiUrl}/users/u1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ is_suspended: true });
    req.flush({
      id: 'u1',
      email: 'a@b.com',
      username: 'sam',
      role: 'user',
      is_suspended: true,
      created_at: '2026-01-01',
    });
    await promise;
  });

  it('deletes a user', async () => {
    const promise = firstValueFrom(service.delete('u1'));
    const req = httpMock.expectOne(`${environment.apiUrl}/users/u1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
    await promise;
  });
});
