import { api } from './client';
import type { RequestConfig } from './client';
import type { RepositoryInsights } from '@/shared/types/insights';

export const insightsService = {
  getInsights(repositoryId: string, config?: RequestConfig): Promise<RepositoryInsights> {
    return api.get(`/analysis/${repositoryId}/insights`, config);
  },
};
