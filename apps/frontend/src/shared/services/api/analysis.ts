import { api } from './client';
import type { RequestConfig } from './client';
import type { AnalysisStartResponse, AnalysisStatusResponse } from './types';

export const analysisService = {
  getStatus(repositoryId: string, config?: RequestConfig): Promise<AnalysisStatusResponse> {
    return api.get(`/analysis/${repositoryId}/status`, config);
  },

  start(repositoryId: string, config?: RequestConfig): Promise<AnalysisStartResponse> {
    return api.post(`/analysis/${repositoryId}/start`, undefined, config);
  },

  cancel(repositoryId: string, config?: RequestConfig): Promise<AnalysisStatusResponse> {
    return api.post(`/analysis/${repositoryId}/cancel`, undefined, config);
  },
};
