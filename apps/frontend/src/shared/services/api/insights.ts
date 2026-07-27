import { api } from './client';
import type { RequestConfig } from './client';
import type { components } from './generated';
import type { RepositoryInsights } from '@/shared/types/insights';

export const insightsService = {
  getInsights(repositoryId: string, config?: RequestConfig): Promise<RepositoryInsights> {
    return api.get<components['schemas']['RepositoryInsightsResponse']>(`/analysis/${repositoryId}/insights`, config)
      .then((response) => ({
        ...response,
        changeOverTime: response.changeOverTime ?? { assessmentState: 'not_assessed', message: 'Change-over-time insights are not available yet.' },
        extractorSet: response.extractorSet ?? [],
        metrics: response.metrics ?? [],
        relationshipsByPredicate: response.relationshipsByPredicate ?? [],
        diagnosticsBySeverity: response.diagnosticsBySeverity ?? [],
        diagnosticsByCode: response.diagnosticsByCode ?? [],
        languages: response.languages ?? [],
      }));
  },
};
