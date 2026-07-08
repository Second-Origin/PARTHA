import { api } from './client';
import type { RequestConfig } from './client';
import type { ReviewResponse } from './types';

export const reviewService = {
  getReview(repositoryId: string, config?: RequestConfig): Promise<ReviewResponse> {
    return api.get(`/analysis/${repositoryId}/review`, config);
  },
};
