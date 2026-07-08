import { api } from './client';
import type { RequestConfig } from './client';
import type { DependencyGraphResponse } from './types';

export const dependencyService = {
  getDependencyGraph(repositoryId: string, config?: RequestConfig): Promise<DependencyGraphResponse> {
    return api.get(`/analysis/${repositoryId}/dependencies`, config);
  },
};
