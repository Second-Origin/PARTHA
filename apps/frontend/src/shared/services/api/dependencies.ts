import { api } from './client';
import type { RequestConfig } from './client';
import type { components } from './generated';
import type { DependencyGraphResponse } from './types';

export const dependencyService = {
  getDependencyGraph(repositoryId: string, config?: RequestConfig): Promise<DependencyGraphResponse> {
    return api.get<components['schemas']['DependencyGraphResponse']>(`/analysis/${repositoryId}/dependencies`, config)
      .then((response) => ({ ...response, diagnostics: response.diagnostics ?? [] }));
  },
};
