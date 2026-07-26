import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { firstValueFrom, isObservable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { redirectToRootGuard } from './redirect-to-root.guard';

describe('redirectToRootGuard', () => {
  let httpMock: HttpTestingController;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    httpMock = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => httpMock.verify());

  function runGuard() {
    return TestBed.runInInjectionContext(() =>
      redirectToRootGuard({} as never, { url: '/bitzas' } as never),
    );
  }

  it('redirects to the root bitza when one exists', async () => {
    const result = runGuard();
    const promise = isObservable(result) ? firstValueFrom(result) : Promise.resolve(result);

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/bitzas/` && r.params.get('root_only') === 'true',
    );
    req.flush([{ id: 'root-1', name: 'The Workshop' }]);

    expect(await promise).toEqual(router.createUrlTree(['/bitzas', 'root-1']));
  });

  it('allows navigation through when no root exists yet', async () => {
    const result = runGuard();
    const promise = isObservable(result) ? firstValueFrom(result) : Promise.resolve(result);

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/bitzas/` && r.params.get('root_only') === 'true',
    );
    req.flush([]);

    expect(await promise).toBe(true);
  });

  it('fails open (allows navigation) if the lookup errors', async () => {
    const result = runGuard();
    const promise = isObservable(result) ? firstValueFrom(result) : Promise.resolve(result);

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/bitzas/` && r.params.get('root_only') === 'true',
    );
    req.flush(null, { status: 500, statusText: 'Server Error' });

    expect(await promise).toBe(true);
  });
});
