import type { components } from '@/shared/services/api/generated';

export type ArchNodeType = components['schemas']['ArchNode']['type'];
export type ArchEdgeType = components['schemas']['ArchEdge']['type'];
export type RelationshipState = components['schemas']['ArchNode']['relationshipState'];
export type TruthClass = components['schemas']['ArchEdge']['truthClass'];
export type ArchNode = components['schemas']['ArchNode'];
export type ArchEvidence = components['schemas']['ArchEvidence'];
export type ArchEdge = components['schemas']['ArchEdge'];
export type ArchitectureDiagnostic = components['schemas']['ArchitectureDiagnostic'];
export type ArchLayer = components['schemas']['ArchLayer'];
export type ArchModule = components['schemas']['ArchModule'];
export type RequestFlowStep = components['schemas']['RequestFlowStep'];
export type ArchitectureSummary = components['schemas']['ArchitectureSummary'];

// These fields have backend defaults, so the generated OpenAPI schema marks
// them optional even though every successful response includes them.
export type ArchitectureModel = components['schemas']['ArchitectureResponse'] &
  Required<Pick<components['schemas']['ArchitectureResponse'], 'diagnostics'>>;

// 'complexity' and 'size' heatmap modes were removed with #217: no repository-
// intelligence producer measures either today, so there was no real signal to
// render. 'usage' (dependents count) and 'critical' are computed only from
// real graph facts.
export type HeatmapMode = 'none' | 'usage' | 'critical';
