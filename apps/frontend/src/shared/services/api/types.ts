import type { components } from './generated';

type WithGeneratedDefaults<T, K extends keyof T> = Omit<T, K> & Required<Pick<T, K>>;

/** Transport helpers retained for non-schema-wrapped legacy endpoints. */
export interface ApiResponse<T> {
  data: T;
  meta?: {
    total?: number;
    page?: number;
    pageSize?: number;
  };
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    total: number;
    page: number;
    pageSize: number;
    totalPages: number;
  };
}

// The aliases below are compatibility names for the existing service/UI
// modules. Their shapes are owned by the generated OpenAPI components; this
// file intentionally contains no hand-maintained DTO fields.
export type RepositoryRevision = components['schemas']['RepositoryRevision'];
export type RepositoryResponse = components['schemas']['RepositoryResponse'];
export type ImportGithubRequest = components['schemas']['GitHubImportRequest'];
export type RepositoryListResponse = components['schemas']['RepositoryListResponse'];
export type RepositoryFileResponse = components['schemas']['RepositoryFileResponse'];

export type RiSchemaVersion = components['schemas']['RiEvidenceResponse']['schemaVersion'];
export type RiPagination = components['schemas']['RiPagination'];
export type RiEvidence = components['schemas']['RiEvidenceResponse'];
export type RiNode = components['schemas']['RiNodeResponse'];
export type RiEdge = components['schemas']['RiEdgeResponse'];
export type RiAssertion = components['schemas']['RiAssertionResponse'];
export type RiSnapshotMetadata = components['schemas']['RiSnapshotMetadataResponse'];
export type RiCollectionResponse<T> = Omit<components['schemas']['RiSymbolsResponse'], 'data'> & { data: T[] };
export type RiPath = components['schemas']['RiPathResponse'];
export type RiNeighboursResponse = components['schemas']['RiNeighboursResponse'];

export type AnalysisJobStatus = components['schemas']['AnalysisStartResponse']['status'];
export type AnalysisStartResponse = components['schemas']['AnalysisStartResponse'];
export type AnalysisStatusResponse = components['schemas']['AnalysisStatusResponse'];

export type ArchitectureResponse = WithGeneratedDefaults<components['schemas']['ArchitectureResponse'], 'diagnostics'>;

export type AuthSchemaVersion = components['schemas']['AuthenticationExplanationResponse']['schemaVersion'];
export type AuthClaimKind = components['schemas']['AuthClaim']['kind'];
export type AuthRelationshipNodeKind = components['schemas']['AuthRelationship']['subjectKind'];
export type AuthConfidence = components['schemas']['AuthClaim']['confidence'];
export type AuthStatus = components['schemas']['AuthenticationExplanationResponse']['status'];
export type AuthEvidenceRef = components['schemas']['AuthEvidenceRef'];
export type AuthClaim = components['schemas']['AuthClaim'];
export type AuthRelationship = components['schemas']['AuthRelationship'];
export type AuthChain = components['schemas']['AuthChain'];
export type AuthenticationDiagnostic = components['schemas']['AuthenticationDiagnostic'];
export type AuthenticationExplanationResponse = WithGeneratedDefaults<
  components['schemas']['AuthenticationExplanationResponse'],
  'claims' | 'relationships' | 'chains' | 'diagnostics'
>;

export type EvidenceSchemaVersion = components['schemas']['EvidenceSourceResponse']['schemaVersion'];
export type EvidenceSourceStatus = components['schemas']['EvidenceSourceResponse']['status'];
export type EvidenceSourceResponse = components['schemas']['EvidenceSourceResponse'];

export type DependencyNode = components['schemas']['DependencyNode'];
export type DependencyDeclaration = components['schemas']['DependencyDeclaration'];
export type DependencyDiagnostic = components['schemas']['DependencyDiagnostic'];
export type DependencyEdge = components['schemas']['DependencyEdge'];
export type DependencyAssessment = components['schemas']['DependencyAssessment'];
export type DependencyProvenance = components['schemas']['DependencyProvenance'];
export type DependencyGraphResponse = WithGeneratedDefaults<components['schemas']['DependencyGraphResponse'], 'diagnostics'>;

export type ReviewResponse = WithGeneratedDefaults<
  components['schemas']['EngineeringReviewResponse'],
  'categories' | 'findings'
>;

export type AiQueryRequest = components['schemas']['AiQueryRequest'];
export type AiMessage = components['schemas']['AiMessage'];
export type AiCitation = components['schemas']['AiCitation'];
export type AiQueryResponse = components['schemas']['AiQueryResponse'];
export type AiProvider = components['schemas']['AiProviderConfig']['provider'];
export type AiProviderConfig = components['schemas']['AiProviderConfig'];
export type AiProviderPublicConfig = components['schemas']['AiProviderPublicConfig'];
export type AiProviderTestRequest = components['schemas']['AiProviderTestRequest'];
export type AiProviderTestResponse = components['schemas']['AiProviderTestResponse'];
export interface AiConversationResponse {
  repositoryId: string;
  messages: AiMessage[];
}

export type GenerateDocRequest = components['schemas']['GenerateDocRequest'];
export type GenerateDocResponse = components['schemas']['GenerateDocResponse'];

export type UserResponse = components['schemas']['UserResponse'];
export type AuthResponse = components['schemas']['AuthResponse'];
export type LoginRequest = components['schemas']['LoginRequest'];
export type RegisterRequest = components['schemas']['RegisterRequest'];

export type ExportFormat = components['schemas']['ExportRequest']['format'];
export type ExportTarget = components['schemas']['ExportRequest']['target'];
export type ExportRequest = components['schemas']['ExportRequest'];
export type ExportResponse = components['schemas']['ExportResponse'];

export type ManifestExtractor = components['schemas']['ManifestExtractor'];
export type RevisionManifest = components['schemas']['RevisionManifest'];
export type RevisionManifestResponse = components['schemas']['RevisionManifestResponse'];
