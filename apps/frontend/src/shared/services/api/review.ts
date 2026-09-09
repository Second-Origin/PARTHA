import { api } from './client';
import type { RequestConfig } from './client';
import type { components } from './generated';
import type { ReviewResponse } from './types';

export interface ReviewQuery {
  category?: string;
  severity?: string;
  diagnosticCode?: string;
  offset?: number;
  limit?: number;
}

export const reviewService = {
  getReview(repositoryId: string, query?: ReviewQuery, config?: RequestConfig): Promise<ReviewResponse> {
    const params = new URLSearchParams();
    if (query?.category) params.set('category', query.category);
    if (query?.severity) params.set('severity', query.severity);
    if (query?.diagnosticCode) params.set('diagnosticCode', query.diagnosticCode);
    if (query?.offset !== undefined) params.set('offset', String(query.offset));
    if (query?.limit !== undefined) params.set('limit', String(query.limit));
    const queryString = params.toString();
    const endpoint = `/analysis/${repositoryId}/review${queryString ? `?${queryString}` : ''}`;
    return api.get<components['schemas']['EngineeringReviewResponse']>(endpoint, config)
      .then((response) => ({ ...response, categories: response.categories ?? [], findings: response.findings ?? [] }));
  },
};
