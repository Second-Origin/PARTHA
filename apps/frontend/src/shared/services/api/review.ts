import { api } from './client';
import type { RequestConfig } from './client';
import type { components } from './generated';
import type { ReviewResponse } from './types';

export const reviewService = {
  getReview(repositoryId: string, config?: RequestConfig): Promise<ReviewResponse> {
    return api.get<components['schemas']['EngineeringReviewResponse']>(`/analysis/${repositoryId}/review`, config)
      .then((response) => ({ ...response, categories: response.categories ?? [], findings: response.findings ?? [] }));
  },
};
