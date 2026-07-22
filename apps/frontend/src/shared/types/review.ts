export type ReviewSeverity = 'critical' | 'high' | 'medium' | 'low';
export type ReviewStatus = 'open' | 'acknowledged' | 'resolved';

export type ReviewCategory =
  | 'architecture'
  | 'security'
  | 'performance'
  | 'maintainability'
  | 'scalability'
  | 'code-quality'
  | 'documentation'
  | 'testing'
  | 'dependency-health'
  | 'configuration';

export interface ReviewFileEvidence {
  path: string;
  sizeBytes: number;
}

export interface ReviewFinding {
  id: string;
  title: string;
  category: ReviewCategory;
  severity: ReviewSeverity;
  status: ReviewStatus;
  problem: string;
  impact: string;
  recommendation: string;
  priority: number;
  estimatedEffort: 'trivial' | 'small' | 'medium' | 'large' | 'major';
  affectedFiles: string[];
  affectedFileDetails: ReviewFileEvidence[];
  affectedModules: string[];
  tags: string[];
}

export interface ReviewScore {
  category: ReviewCategory;
  score: number;
  trend: 'improving' | 'stable' | 'declining';
  riskLevel: ReviewSeverity;
  priority: number;
  findingsCount: number;
}

export interface ReviewSummary {
  overallScore: number;
  overallTrend: 'improving' | 'stable' | 'declining';
  criticalCount: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  totalFindings: number;
}

export interface ImprovementStep {
  id: string;
  title: string;
  description: string;
  priority: ReviewSeverity;
  estimatedEffort: string;
  category: ReviewCategory;
  relatedFindings: string[];
}

export interface EngineeringReview {
  repositoryId: string;
  repositoryName: string;
  generatedAt: string;
  summary: ReviewSummary;
  scores: ReviewScore[];
  findings: ReviewFinding[];
  roadmap: ImprovementStep[];
}
