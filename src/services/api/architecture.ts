import { api } from './client';
import type { RequestConfig } from './client';
import type { ArchitectureResponse } from './types';

export const architectureService = {
  getArchitecture(repositoryId: string, config?: RequestConfig): Promise<ArchitectureResponse> {
    return api.get(`/analysis/${repositoryId}/architecture`, config);
  },
};
