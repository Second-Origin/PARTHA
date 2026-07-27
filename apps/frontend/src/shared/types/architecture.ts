export type ArchNodeType =
  | 'frontend'
  | 'backend'
  | 'controller'
  | 'route'
  | 'service'
  | 'repository'
  | 'database'
  | 'configuration'
  | 'authentication'
  | 'middleware'
  | 'utilities'
  | 'models'
  | 'external-api'
  | 'shared-library'
  | 'environment'
  | 'queue'
  | 'cache';

export type ArchEdgeType = 'dependency' | 'import' | 'api-call' | 'data-flow' | 'event' | 'reads' | 'writes' | 'calls' | 'config-usage';
export type RelationshipState = 'connected' | 'no-observed-relationships' | 'unresolved' | 'not-extracted';
export type TruthClass = 'resolved' | 'inferred';

// 'complexity' and 'size' heatmap modes were removed with #217: no repository-
// intelligence producer measures either today, so there was no real signal to
// render. 'usage' (dependents count) and 'critical' are computed only from
// real graph facts.
export type HeatmapMode = 'none' | 'usage' | 'critical';

export interface ArchNode {
  id: string;
  name: string;
  type: ArchNodeType;
  description: string;
  responsibilities: string[];
  files: string[];
  dependencies: string[];
  dependents: string[];
  // No producer measures complexity or line counts today (#217); 'not_computed'
  // is explicit and must never be synthesized from an unrelated real value
  // (e.g. file count).
  estimatedComplexity: 'low' | 'medium' | 'high' | 'not_computed';
  estimatedLines: number | 'not_computed';
  tags: string[];
  layer: string;
  parentModule?: string;
  relationshipState: RelationshipState;
}

export interface ArchEvidence {
  snapshotId: string;
  factId: string;
  path: string;
  startLine: number;
  endLine: number;
}

export interface ArchEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  type: ArchEdgeType;
  predicate: string;
  truthClass: TruthClass;
  evidence: ArchEvidence[];
}

export interface ArchitectureDiagnostic {
  code: string;
  category: string;
  severity: 'fatal' | 'error' | 'warning' | 'info';
  message: string;
  path?: string;
  startLine?: number;
  endLine?: number;
  subjectKey?: string;
  objectKey?: string;
  details?: Record<string, unknown>;
  nodeIds?: string[];
}

export interface ArchLayer {
  id: string;
  name: string;
  order: number;
  nodes: string[];
}

export interface ArchModule {
  id: string;
  name: string;
  layer: string;
  nodeIds: string[];
  description: string;
  fileCount: number;
}

export interface RequestFlowStep {
  id: string;
  name: string;
  type: ArchNodeType;
  description: string;
  details: string[];
}

export interface ArchitectureModel {
  repositoryId: string;
  repositoryName: string;
  architectureType: string;
  detectedLayers: ArchLayer[];
  nodes: ArchNode[];
  edges: ArchEdge[];
  modules: ArchModule[];
  requestFlow: RequestFlowStep[];
  relationshipSnapshotId?: string;
  diagnostics: ArchitectureDiagnostic[];
  summary: {
    language: string;
    framework: string;
    totalModules: number;
    totalNodes: number;
    entryPoint: string;
    architecturePattern: string;
  };
}
