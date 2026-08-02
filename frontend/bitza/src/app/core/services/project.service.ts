import { HttpClient, HttpParams } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  MyProjectMembership,
  Project,
  ProjectCreate,
  ProjectListItem,
  ProjectMember,
  ProjectMemberCreate,
  ProjectUpdate,
} from '../models';

@Service()
export class ProjectService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/projects`;

  /** Omit userId for every project; pass it to filter to one user's projects. */
  list(userId?: string): Observable<ProjectListItem[]> {
    const params = userId ? new HttpParams().set('user_id', userId) : undefined;
    return this.http.get<ProjectListItem[]>(`${this.baseUrl}/`, { params });
  }

  get(id: string): Observable<Project> {
    return this.http.get<Project>(`${this.baseUrl}/${id}`);
  }

  create(project: ProjectCreate): Observable<Project> {
    return this.http.post<Project>(`${this.baseUrl}/`, project);
  }

  update(id: string, project: ProjectUpdate): Observable<Project> {
    return this.http.patch<Project>(`${this.baseUrl}/${id}`, project);
  }

  /** 409 if any bitza still references this project as responsible_project_id. */
  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }

  listMembers(projectId: string): Observable<ProjectMember[]> {
    return this.http.get<ProjectMember[]>(`${this.baseUrl}/${projectId}/members`);
  }

  addMember(projectId: string, member: ProjectMemberCreate): Observable<ProjectMember> {
    return this.http.post<ProjectMember>(`${this.baseUrl}/${projectId}/members`, member);
  }

  /** Sets or unsets this membership as the user's primary project. */
  setPrimary(projectId: string, userId: string, isPrimary: boolean): Observable<ProjectMember> {
    return this.http.patch<ProjectMember>(`${this.baseUrl}/${projectId}/members/${userId}`, {
      is_primary: isPrimary,
    });
  }

  removeMember(projectId: string, userId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${projectId}/members/${userId}`);
  }

  /**
   * The current user's own memberships, with the is_primary flag —
   * powers the '/me' page. Always scoped server-side to the caller,
   * unlike list(userId), which can look up any user's projects.
   */
  listMine(): Observable<MyProjectMembership[]> {
    return this.http.get<MyProjectMembership[]>(`${this.baseUrl}/mine`);
  }
}
