import type { components } from '@/shared/services/api/generated';

export type InsightAssessmentState = components['schemas']['InsightMetric']['assessmentState'];
export type InsightProvenance = components['schemas']['InsightProvenance'];
export type InsightExtractor = components['schemas']['InsightExtractor'];
export type InsightMetric = components['schemas']['InsightMetric'];
export type InsightBreakdown = components['schemas']['InsightBreakdown'];

export type RepositoryInsights = components['schemas']['RepositoryInsightsResponse'] & Required<
  Pick<
    components['schemas']['RepositoryInsightsResponse'],
    'changeOverTime' | 'extractorSet' | 'metrics' | 'relationshipsByPredicate' |
      'diagnosticsBySeverity' | 'diagnosticsByCode' | 'languages'
  >
>;
