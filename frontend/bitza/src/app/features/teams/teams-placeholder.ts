import { Component, inject } from '@angular/core';
import { AppConfigService } from '../../core/services/app-config.service';

@Component({
  selector: 'app-teams-placeholder',
  template: `
    <h1>{{ config.teamLabelPlural() }}</h1>
    <p>{{ config.teamLabelSingular() }} management lands in Milestone 2 of the frontend build.</p>
  `,
})
export class TeamsPlaceholder {
  protected readonly config = inject(AppConfigService);
}
