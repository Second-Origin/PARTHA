import { api } from './client';
import type { RequestConfig } from './client';
import type {
  RepositoryResponse,
  RepositoryListResponse,
  ImportGithubRequest,
} from './types';

export const repositoryService = {
  list(config?: RequestConfig): Promise<RepositoryListResponse> {
    return api.get('/repositories', config);
  },

  getById(id: string, config?: RequestConfig): Promise<RepositoryResponse> {
    return api.get(`/repositories/${id}`, config);
  },

  delete(id: string, config?: RequestConfig): Promise<void> {
    return api.delete(`/repositories/${id}`, config);
  },

  importFromGithub(request: ImportGithubRequest, config?: RequestConfig): Promise<RepositoryResponse> {
    return api.post('/repositories/github', request, config);
  },
};
