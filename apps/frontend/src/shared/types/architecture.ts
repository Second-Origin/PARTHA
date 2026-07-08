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
}

export interface ArchEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  type: ArchEdgeType;
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
  summary: {
    language: string;
    framework: string;
    totalModules: number;
    totalNodes: number;
    entryPoint: string;
    architecturePattern: string;
  };
}
