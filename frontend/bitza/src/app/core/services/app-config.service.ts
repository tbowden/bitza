import { Service, computed, signal } from '@angular/core';

export type TeamLabelMode = 'team' | 'project';

const LABEL_MODE_KEY = 'bitza_team_label_mode';

/**
 * "Team" vs "Project" is a pure display-label choice — the API is always
 * `Team` (see bitza_project_context.md). This was an open question in the
 * restoration doc ("where the toggle actually lives"); implemented here as
 * a runtime setting rather than a build-time environment file, so a single
 * deployment can be reconfigured (e.g. from an admin settings screen, once
 * one exists) without a rebuild. Persisted to localStorage so a club's
 * chosen wording survives a reload.
 */
@Service()
export class AppConfigService {
  private readonly mode = signal<TeamLabelMode>(this.readInitialMode());

  readonly teamLabelMode = this.mode.asReadonly();

  readonly teamLabelSingular = computed(() => (this.mode() === 'project' ? 'Project' : 'Team'));

  readonly teamLabelPlural = computed(() => (this.mode() === 'project' ? 'Projects' : 'Teams'));

  setTeamLabelMode(mode: TeamLabelMode): void {
    this.mode.set(mode);
    localStorage.setItem(LABEL_MODE_KEY, mode);
  }

  private readInitialMode(): TeamLabelMode {
    const stored = localStorage.getItem(LABEL_MODE_KEY);
    return stored === 'project' ? 'project' : 'team';
  }
}
