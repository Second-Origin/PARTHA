import { api } from './client';
import type { RequestConfig } from './client';
import type { components } from './generated';
import type {
  RepositoryResponse,
  RepositoryListResponse,
  RepositoryFileResponse,
  ImportGithubRequest,
  RiNeighboursResponse,
  RiSnapshotMetadata,
} from './types';

export const repositoryService = {
  list(config?: RequestConfig): Promise<RepositoryListResponse> {
    return api.get('/repositories', config);
  },

  getById(id: string, config?: RequestConfig): Promise<RepositoryResponse> {
    return api.get(`/repositories/${id}`, config);
  },

  getFile(id: string, path: string, config?: RequestConfig): Promise<RepositoryFileResponse> {
    return api.get(`/repositories/${id}/file?path=${encodeURIComponent(path)}`, config);
  },

  delete(id: string, config?: RequestConfig): Promise<void> {
    return api.delete(`/repositories/${id}`, config);
  },

  importFromGithub(request: ImportGithubRequest, config?: RequestConfig): Promise<RepositoryResponse> {
    return api.post('/repositories/github', request, config);
  },
};

export const repositoryIntelligenceService = {
  getSnapshot(snapshotId: string, config?: RequestConfig): Promise<RiSnapshotMetadata> {
    return api.get(`/intelligence/v1/snapshots/${encodeURIComponent(snapshotId)}`, config);
  },

  listSymbols(snapshotId: string, offset = 0, limit = 50, config?: RequestConfig): Promise<components['schemas']['RiSymbolsResponse']> {
    return api.get(`/intelligence/v1/snapshots/${encodeURIComponent(snapshotId)}/symbols?offset=${offset}&limit=${limit}`, config);
  },

  listNeighbours(snapshotId: string, nodeKey: string, offset = 0, limit = 50, config?: RequestConfig): Promise<RiNeighboursResponse> {
    return api.get(`/intelligence/v1/snapshots/${encodeURIComponent(snapshotId)}/neighbours?nodeKey=${encodeURIComponent(nodeKey)}&offset=${offset}&limit=${limit}`, config);
  },

  listReferences(snapshotId: string, offset = 0, limit = 50, config?: RequestConfig): Promise<components['schemas']['RiReferencesResponse']> {
    return api.get(`/intelligence/v1/snapshots/${encodeURIComponent(snapshotId)}/references?offset=${offset}&limit=${limit}`, config);
  },

  listAssertions(snapshotId: string, offset = 0, limit = 50, config?: RequestConfig): Promise<components['schemas']['RiAssertionsResponse']> {
    return api.get(`/intelligence/v1/snapshots/${encodeURIComponent(snapshotId)}/assertions?offset=${offset}&limit=${limit}`, config);
  },

  listPaths(snapshotId: string, offset = 0, limit = 50, config?: RequestConfig): Promise<components['schemas']['RiPathsResponse']> {
    return api.get(`/intelligence/v1/snapshots/${encodeURIComponent(snapshotId)}/paths?offset=${offset}&limit=${limit}`, config);
  },

  listEvidence(snapshotId: string, offset = 0, limit = 50, config?: RequestConfig): Promise<components['schemas']['RiEvidenceResponsePage']> {
    return api.get(`/intelligence/v1/snapshots/${encodeURIComponent(snapshotId)}/evidence?offset=${offset}&limit=${limit}`, config);
  },
};
