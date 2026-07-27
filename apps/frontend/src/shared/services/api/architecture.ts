import { api } from './client';
import type { RequestConfig } from './client';
import type { components } from './generated';
import type {
  ArchitectureResponse,
  AuthenticationExplanationResponse,
  EvidenceSourceResponse,
  RevisionManifestResponse,
} from './types';

export const architectureService = {
  getArchitecture(repositoryId: string, config?: RequestConfig): Promise<ArchitectureResponse> {
    return api.get<components['schemas']['ArchitectureResponse']>(`/analysis/${repositoryId}/architecture`, config)
      .then((response) => ({ ...response, diagnostics: response.diagnostics ?? [] }));
  },

  getAuthenticationExplanation(
    repositoryId: string,
    config?: RequestConfig,
  ): Promise<AuthenticationExplanationResponse> {
    return api.get<components['schemas']['AuthenticationExplanationResponse']>(
      `/analysis/${repositoryId}/architecture/authentication`, config,
    ).then((response) => ({
      ...response,
      claims: response.claims ?? [],
      relationships: response.relationships ?? [],
      chains: response.chains ?? [],
      diagnostics: response.diagnostics ?? [],
    }));
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
