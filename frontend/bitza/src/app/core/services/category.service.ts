import { HttpClient } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Category, CategoryCreate, CategoryUpdate } from '../models';

@Service()
export class CategoryService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/categories`;

  list(): Observable<Category[]> {
    return this.http.get<Category[]>(`${this.baseUrl}/`);
  }

  create(category: CategoryCreate): Observable<Category> {
    return this.http.post<Category>(`${this.baseUrl}/`, category);
  }

  update(id: string, category: CategoryUpdate): Observable<Category> {
    return this.http.patch<Category>(`${this.baseUrl}/${id}`, category);
  }

  /** Blocked by the backend while any bitza still references this category. */
  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
