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
export interface RepositoryResponse {
  id: string;
  name: string;
  description: string | null;
  source: 'upload' | 'github';
  sourceUrl: string | null;
  branch?: string | null;
  size: number;
  fileCount: number;
  status: 'uploading' | 'analysing' | 'completed' | 'error';
  dataSource: DataSource;
  analysisStage: AnalysisStage | null;
  analysisProgress: number;
  uploadedAt: string;
  analysedAt: string | null;
  errorMessage: string | null;
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

// Analysis
export interface AnalysisStartResponse {
  repositoryId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
}

export interface AnalysisStatusResponse {
  repositoryId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  stage: AnalysisStage | null;
  progress: number;
  startedAt: string | null;
  completedAt: string | null;
  error: string | null;
}

// Architecture
export type ArchitectureResponse = ArchitectureModel;

// Dependency Graph
export interface DependencyNode {
  id: string;
  name: string;
  version: string;
  type: 'production' | 'development' | 'peer' | 'optional';
  hasVulnerabilities: boolean;
  isOutdated: boolean;
  size: number | null;
}

export interface DependencyEdge {
  source: string;
  target: string;
  type: 'depends-on' | 'peer' | 'optional';
}

export interface DependencyGraphResponse {
  repositoryId: string;
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  totalDependencies: number;
  vulnerabilities: number;
  outdated: number;
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

export interface AiStreamChunk {
  type: 'content' | 'citation' | 'done' | 'error';
  content?: string;
  citation?: AiCitation;
  error?: string;
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
