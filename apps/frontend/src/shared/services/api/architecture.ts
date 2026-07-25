import { api } from './client';
import type { RequestConfig } from './client';
import type {
  ArchitectureResponse,
  AuthenticationExplanationResponse,
  EvidenceSourceResponse,
  RevisionManifestResponse,
} from './types';

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

  getRevisionManifest(repositoryId: string, config?: RequestConfig): Promise<RevisionManifestResponse> {
    return api.get(`/analysis/${repositoryId}/revision-manifest`, config);
  },

  getEvidenceSource(
    repositoryId: string,
    snapshotId: string,
    factId: string,
    path: string,
    startLine: number,
    endLine: number,
    config?: RequestConfig,
  ): Promise<EvidenceSourceResponse> {
    const params = new URLSearchParams({
      snapshotId,
      factId,
      path,
      startLine: String(startLine),
      endLine: String(endLine),
    });
    return api.get(`/analysis/${repositoryId}/evidence?${params.toString()}`, config);
  },
};
