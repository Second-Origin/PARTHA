import type { components } from '@/shared/services/api/generated';

export type ReviewSeverity = components['schemas']['ReviewFinding']['severity'];
export type ReviewAssessmentState = components['schemas']['ReviewCategoryAssessment']['state'];
export type ReviewCategory = components['schemas']['ReviewCategoryAssessment']['id'];
export type ReviewSupportStatus = components['schemas']['ReviewFinding']['supportStatus'];
export type ReviewProvenance = components['schemas']['ReviewProvenance'];
export type ReviewEvidenceReference = components['schemas']['ReviewEvidenceReference'];
export type ReviewFinding = components['schemas']['ReviewFinding'];
export type ReviewCategoryAssessment = components['schemas']['ReviewCategoryAssessment'];
export type ReviewSeverityCounts = components['schemas']['ReviewSeverityCounts'];
export type ReviewSummary = components['schemas']['ReviewSummary'];
export type ReviewPagination = components['schemas']['ReviewPagination'];

export type EngineeringReview = components['schemas']['EngineeringReviewResponse'] &
  Required<Pick<components['schemas']['EngineeringReviewResponse'], 'categories' | 'findings'>>;
