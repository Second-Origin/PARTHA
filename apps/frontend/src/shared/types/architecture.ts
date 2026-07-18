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

export type HeatmapMode = 'none' | 'complexity' | 'usage' | 'size' | 'critical';

export interface ArchNode {
  id: string;
  name: string;
  type: ArchNodeType;
  description: string;
  responsibilities: string[];
  files: string[];
  dependencies: string[];
  dependents: string[];
  estimatedComplexity: 'low' | 'medium' | 'high';
  estimatedLines: number;
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
