import { HttpClient, HttpParams } from '@angular/common/http';
import { Service, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Team, TeamCreate, TeamMember, TeamMemberCreate, TeamUpdate } from '../models';

@Service()
export class TeamService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiUrl}/teams`;

  /** Omit userId for every team; pass it to filter to one user's teams. */
  list(userId?: string): Observable<Team[]> {
    const params = userId ? new HttpParams().set('user_id', userId) : undefined;
    return this.http.get<Team[]>(`${this.baseUrl}/`, { params });
  }

  get(id: string): Observable<Team> {
    return this.http.get<Team>(`${this.baseUrl}/${id}`);
  }

  create(team: TeamCreate): Observable<Team> {
    return this.http.post<Team>(`${this.baseUrl}/`, team);
  }

  update(id: string, team: TeamUpdate): Observable<Team> {
    return this.http.patch<Team>(`${this.baseUrl}/${id}`, team);
  }

  /** 409 if any bitza still references this team as responsible_team_id. */
  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }

  listMembers(teamId: string): Observable<TeamMember[]> {
    return this.http.get<TeamMember[]>(`${this.baseUrl}/${teamId}/members`);
  }

  addMember(teamId: string, member: TeamMemberCreate): Observable<TeamMember> {
    return this.http.post<TeamMember>(`${this.baseUrl}/${teamId}/members`, member);
  }

  /** Sets or unsets this membership as the user's primary team. */
  setPrimary(teamId: string, userId: string, isPrimary: boolean): Observable<TeamMember> {
    return this.http.patch<TeamMember>(`${this.baseUrl}/${teamId}/members/${userId}`, {
      is_primary: isPrimary,
    });
  }

  removeMember(teamId: string, userId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${teamId}/members/${userId}`);
  }
}
