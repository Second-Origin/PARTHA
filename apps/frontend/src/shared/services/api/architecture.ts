import { api } from './client';
import type { RequestConfig } from './client';
import type { ArchitectureResponse, AuthenticationExplanationResponse } from './types';

export const architectureService = {
  getArchitecture(repositoryId: string, config?: RequestConfig): Promise<ArchitectureResponse> {
    return api.get(`/analysis/${repositoryId}/architecture`, config);
  },

  getAuthenticationExplanation(
    repositoryId: string,
    config?: RequestConfig,
  ): Promise<AuthenticationExplanationResponse> {
    return api.get(`/analysis/${repositoryId}/architecture/authentication`, config);
  },
};
