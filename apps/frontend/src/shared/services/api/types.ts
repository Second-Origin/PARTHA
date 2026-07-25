import type { DataSource, FileTreeNode, RepositoryMeta, AnalysisStage } from '@/shared/types';
import type { ArchitectureModel } from '@/shared/types/architecture';
import type { EngineeringReview } from '@/shared/types/review';

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

// Repository

// First-class revision identity (#87). `value` is the immutable identity: a
// 40-char lowercase git commit SHA for GitHub imports, or a `sha256:<hex>`
// archive content hash for uploads. `ref` (e.g. `refs/heads/main`) is a moving
// pointer — descriptive metadata only, never identity, and null for uploads.
export interface RepositoryRevision {
  kind: 'git' | 'upload';
  value: string;
  ref: string | null;
}

export interface RepositoryResponse {
  id: string;
  name: string;
  description: string | null;
  source: 'upload' | 'github';
  sourceUrl: string | null;
  branch?: string | null;
  size: number;
  fileCount: number;
  status: 'uploading' | 'analysing' | 'completed' | 'cancelled' | 'error';
  dataSource: DataSource;
  analysisStage: AnalysisStage | null;
  analysisProgress: number;
  uploadedAt: string;
  analysedAt: string | null;
  errorMessage: string | null;
  revision: RepositoryRevision | null;
  // Backward-compatible alias of `revision.value`.
  commitSha: string | null;
  meta: RepositoryMeta | null;
  fileTree: FileTreeNode[];
}

export interface CreateRepositoryRequest {
  name: string;
  description?: string;
  source: 'upload' | 'github';
  sourceUrl?: string;
}

export interface ImportGithubRequest {
  url: string;
  branch?: string;
}

export interface RepositoryListResponse {
  data: RepositoryResponse[];
  total: number;
}

export interface RepositoryFileResponse {
  path: string;
  content: string;
  size: number;
  truncated: boolean;
  isBinary: boolean;
  isImage: boolean;
  mediaType: string | null;
}

// Repository Intelligence snapshot queries (`/intelligence/v1`). These are
// read-only views of sealed, owner-scoped normalized facts, not legacy metadata.
export type RiSchemaVersion = 'ri.v1';

export interface RiPagination {
  offset: number;
  limit: number;
  total: number;
}

export interface RiEvidence {
  schemaVersion: RiSchemaVersion;
  factKind: 'node' | 'edge' | 'observation';
  factId: string;
  path: string;
  startLine: number;
  endLine: number;
  granularity: 'span' | 'file';
  extractor: string;
  extractorVersion: string;
}

export interface RiNode {
  stableKey: string;
  nodeKind: string;
  name: string | null;
  language: string | null;
  truthClass: 'observed';
  properties: Record<string, unknown> | null;
  evidence: RiEvidence[];
}

export interface RiEdge {
  edgeId: string;
  subjectKind: string;
  subjectKey: string;
  predicate: string;
  objectKind: string;
  objectKey: string;
  truthClass: 'resolved';
  producer: string;
  producerVersion: string;
  evidence: RiEvidence[];
  derivedFrom: Array<{ kind: string; identity: string }>;
}

export interface RiAssertion {
  assertionId: string;
  subjectKind: string;
  subjectKey: string;
  predicate: string;
  value: Record<string, unknown>;
  truthClass: 'inferred';
  producer: string;
  producerVersion: string;
  derivedFrom: Array<{ kind: string; identity: string }>;
}

export interface RiSnapshotMetadata {
  schemaVersion: RiSchemaVersion;
  snapshotId: string;
  repositoryId: string;
  revisionKind: 'git' | 'upload';
  revisionValue: string;
  revisionRef: string | null;
  state: 'completed';
  producerVersionSet: string[];
  producerSetHash: string;
  configHash: string;
  canonicalGraphHash: string;
  createdAt: string;
  updatedAt: string;
  sealedAt: string;
}

export interface RiCollectionResponse<T> {
  schemaVersion: RiSchemaVersion;
  data: T[];
  pagination: RiPagination;
}

export interface RiPath {
  path: string;
  node: RiNode;
}

export interface RiNeighboursResponse extends RiCollectionResponse<RiEdge> {
  nodeKey: string;
}

// Analysis
export type AnalysisJobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface AnalysisStartResponse {
  repositoryId: string;
  status: AnalysisJobStatus;
  jobId: string | null;
}

export interface AnalysisStatusResponse {
  repositoryId: string;
  status: AnalysisJobStatus;
  jobId: string | null;
  stage: AnalysisStage | null;
  progress: number;
  startedAt: string | null;
  completedAt: string | null;
  error: string | null;
}

// Architecture
export type ArchitectureResponse = ArchitectureModel;

// Authentication explanation (evidence-backed, snapshot-only)
export type AuthSchemaVersion = 'auth-explanation.v1';
export type AuthClaimKind = 'route' | 'middleware' | 'service' | 'model' | 'dependency';
export type AuthRelationshipNodeKind = 'route' | 'handler' | 'middleware' | 'service' | 'model' | 'dependency';
export type AuthConfidence = 'observed' | 'heuristic';
export type AuthStatus = 'ready' | 'missing_snapshot';

export interface AuthEvidenceRef {
  snapshotId: string;
  factId: string;
  path: string;
  startLine: number;
  endLine: number;
}

export interface AuthClaim {
  kind: AuthClaimKind;
  name: string;
  confidence: AuthConfidence;
  evidence: AuthEvidenceRef[];
}

export interface AuthRelationship {
  subject: string;
  subjectKind: AuthRelationshipNodeKind;
  predicate: string;
  object: string;
  objectKind: AuthRelationshipNodeKind;
  evidence: AuthEvidenceRef[];
}

export interface AuthChain {
  route: string;
  hops: AuthRelationship[];
}

export interface AuthenticationDiagnostic {
  code: string;
  category: string;
  severity: 'fatal' | 'error' | 'warning' | 'info';
  message: string;
  path: string | null;
  startLine: number | null;
  endLine: number | null;
}

export interface AuthenticationExplanationResponse {
  schemaVersion: AuthSchemaVersion;
  repositoryId: string;
  repositoryName: string;
  revisionKind: string | null;
  revisionValue: string | null;
  snapshotId: string | null;
  status: AuthStatus;
  summary: string;
  claims: AuthClaim[];
  relationships: AuthRelationship[];
  chains: AuthChain[];
  diagnostics: AuthenticationDiagnostic[];
}

// Evidence-source navigation (snapshot-and-revision-verified, #95)
export type EvidenceSchemaVersion = 'evidence-source.v1';
export type EvidenceSourceStatus = 'ready' | 'unavailable';

export interface EvidenceSourceResponse {
  schemaVersion: EvidenceSchemaVersion;
  repositoryId: string;
  snapshotId: string;
  factId: string;
  revisionKind: string | null;
  revisionValue: string | null;
  path: string;
  startLine: number;
  endLine: number;
  status: EvidenceSourceStatus;
  reason: string | null;
  content: string | null;
  truncated: boolean;
  size: number;
}

// Dependency Graph
export interface DependencyNode {
  id: string;
  name: string;
  version: string | null;
  type: 'production' | 'development' | 'peer' | 'optional' | 'multiple';
  ecosystem: string;
  declarations: DependencyDeclaration[];
  size: number | null;
}

export interface DependencyDeclaration {
  name: string;
  manifestPath: string;
  workspacePath: string;
  startLine: number;
  endLine: number;
  extractor: string;
  extractorVersion: string;
  ecosystem: string;
  version: string | null;
  type: 'production' | 'development' | 'peer' | 'optional';
}

export interface DependencyDiagnostic {
  code: string;
  category: string;
  severity: 'fatal' | 'error' | 'warning' | 'info';
  message: string;
  path: string | null;
  producer: string;
  details: Record<string, unknown> | null;
}

export interface DependencyEdge {
  source: string;
  target: string;
  type: 'depends-on' | 'peer' | 'optional';
}

export interface DependencyAssessment {
  status: 'not_computed';
}

/**
 * Which intelligence path produced a repository-derived response. `ri.v1` is
 * the sealed, evidence-backed snapshot model; `legacy-heuristic` is the older
 * engine that reads mutable repository metadata. Legacy responses always carry
 * a limitation so a heuristic result is never shown as snapshot-backed.
 */
export interface IntelligenceProvenance {
  source: 'ri.v1' | 'legacy-heuristic';
  limitation: string | null;
}

export interface DependencyGraphResponse {
  repositoryId: string;
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  totalDependencies: number;
  manifestCount: number;
  diagnostics: DependencyDiagnostic[];
  vulnerabilityAssessment: DependencyAssessment;
  outdatedAssessment: DependencyAssessment;
  provenance: IntelligenceProvenance;
}

// Review
export type ReviewResponse = EngineeringReview;

// AI
export interface AiQueryRequest {
  repositoryId: string;
  query: string;
  context?: {
    selectedNodeId?: string;
    selectedFile?: string;
    conversationHistory?: AiMessage[];
  };
}

export interface AiMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: AiCitation[];
}

export interface AiCitation {
  file: string;
  startLine: number;
  endLine: number;
  content: string;
}

export interface AiQueryResponse {
  message: AiMessage;
  suggestions?: string[];
}

export type AiProvider = 'openai' | 'anthropic' | 'gemini' | 'openrouter' | 'ollama';

export interface AiProviderConfig {
  provider: AiProvider;
  apiKey?: string;
  model?: string;
  baseUrl?: string;
}

export interface AiProviderPublicConfig {
  provider: AiProvider | null;
  model: string | null;
  baseUrl: string | null;
  hasApiKey: boolean;
  // Write-only key contract: the backend returns only the last four characters,
  // never the full key. Null when no key is stored.
  apiKeyLast4: string | null;
}

export interface AiProviderTestRequest {
  provider?: AiProvider;
  apiKey?: string;
  model?: string;
  baseUrl?: string;
}

export interface AiProviderTestResponse {
  ok: boolean;
  message: string;
  checkedAt: string;
}

// Documentation
export interface GenerateDocRequest {
  repositoryId: string;
  format: 'markdown' | 'html';
  sections?: string[];
}

export interface GenerateDocResponse {
  content: string;
  format: 'markdown' | 'html';
  generatedAt: string;
}

// Auth
export interface UserResponse {
  id: string;
  email: string;
  createdAt: string;
}

export interface AuthResponse {
  accessToken: string;
  tokenType: 'bearer';
  user: UserResponse;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

// Export
export type ExportFormat = 'json' | 'markdown' | 'html' | 'pdf';
export type ExportTarget = 'review' | 'documentation' | 'architecture' | 'dependencies';

export interface ExportRequest {
  repositoryId: string;
  target: ExportTarget;
  format: ExportFormat;
}

export interface ExportResponse {
  filename: string;
  mediaType: string;
  encoding: 'utf-8' | 'base64';
  content: string;
}

// Revision manifest (#113): the verifiable identity of the sealed snapshot an
// answer was derived from. `manifestDigest` is a canonical content hash, not a
// digital signature.
export interface ManifestExtractor {
  name: string;
  version: string;
}

export interface RevisionManifest {
  schemaVersion: 'revision-manifest.v1';
  repositoryId: string;
  revisionKind: 'git' | 'upload';
  revisionValue: string;
  revisionRef: string | null;
  snapshotId: string;
  snapshotSchemaVersion: string;
  extractors: ManifestExtractor[];
  producerSetHash: string;
  configHash: string;
  canonicalGraphHash: string | null;
  createdAt: string;
  sealedAt: string | null;
}

export interface RevisionManifestResponse {
  manifest: RevisionManifest;
  manifestDigest: string;
  verificationMethod: string;
  verificationState: 'verified' | 'superseded' | 'mismatch' | 'unverifiable';
  verificationNote: string;
}
