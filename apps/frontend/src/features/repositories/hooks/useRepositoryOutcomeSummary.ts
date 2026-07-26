import { useEffect, useState } from 'react';
import type { Repository } from '@/shared/types';
import type { EngineeringReview, ReviewSeverity } from '@/shared/types/review';
import { backendService } from '@/shared/services/backend';

export type OutcomeAssessmentState = 'loading' | 'assessed' | 'not_assessed';

export interface RepositoryOutcomeSummary {
  stack: {
    state: OutcomeAssessmentState;
    language: string | null;
    framework: string | null;
    architecturePattern: string | null;
  };
  structure: {
    state: OutcomeAssessmentState;
    totalModules: number | null;
    totalNodes: number | null;
  };
  dependencies: {
    state: OutcomeAssessmentState;
    totalDependencies: number | null;
  };
  headline: {
    state: OutcomeAssessmentState;
    message: string | null;
    severity: ReviewSeverity | null;
  };
  coverage: {
    state: OutcomeAssessmentState;
    extractorCount: number | null;
    languageCount: number | null;
  };
}

const LOADING_SUMMARY: RepositoryOutcomeSummary = {
  stack: { state: 'loading', language: null, framework: null, architecturePattern: null },
  structure: { state: 'loading', totalModules: null, totalNodes: null },
  dependencies: { state: 'loading', totalDependencies: null },
  headline: { state: 'loading', message: null, severity: null },
  coverage: { state: 'loading', extractorCount: null, languageCount: null },
};

const SEVERITY_ORDER: ReviewSeverity[] = ['critical', 'high', 'medium', 'low', 'info'];

function headlineFromReview(review: EngineeringReview): { message: string; severity: ReviewSeverity | null } {
  for (const severity of SEVERITY_ORDER) {
    const count = review.summary.findingsBySeverity[severity];
    if (count > 0) {
      return { message: `${count} ${severity}-severity finding${count === 1 ? '' : 's'}`, severity };
    }
  }
  return { message: 'No evidence-backed findings were surfaced', severity: null };
}

/**
 * Composes the repository landing summary purely from existing sealed-snapshot
 * read APIs (Architecture, Review, Dependencies, Insights) -- no LLM, no
 * client-side computation of anything the backend doesn't already expose.
 * Each section fails independently to `not_assessed`: a repository can be
 * `completed` without a sealed ri.v1 snapshot yet (the same 404 contract
 * Architecture/Review/Insights/Dependencies already surface individually), and
 * this is a lightweight preview, not a substitute for those pages' own
 * detailed error/retry states.
 */
export function useRepositoryOutcomeSummary(repository: Repository | null): RepositoryOutcomeSummary {
  const [summary, setSummary] = useState<RepositoryOutcomeSummary>(LOADING_SUMMARY);
  const repositoryId = repository?.status === 'completed' ? repository.id : null;

  useEffect(() => {
    if (!repository || repositoryId === null) {
      setSummary(LOADING_SUMMARY);
      return;
    }

    let cancelled = false;
    setSummary(LOADING_SUMMARY);

    async function load() {
      const [architectureResult, reviewResult, dependenciesResult, insightsResult] = await Promise.allSettled([
        backendService.fetchArchitecture(repository as Repository),
        backendService.fetchReview(repository as Repository),
        backendService.fetchDependencyGraph(repositoryId as string),
        backendService.fetchInsights(repository as Repository),
      ]);
      if (cancelled) return;

      const architecture = architectureResult.status === 'fulfilled' ? architectureResult.value : null;
      const review = reviewResult.status === 'fulfilled' ? reviewResult.value : null;
      const dependencies = dependenciesResult.status === 'fulfilled' ? dependenciesResult.value : null;
      const insights = insightsResult.status === 'fulfilled' ? insightsResult.value : null;
      const headline = review ? headlineFromReview(review) : null;

      setSummary({
        stack: architecture
          ? {
              state: 'assessed',
              language: architecture.summary.language,
              framework: architecture.summary.framework,
              architecturePattern: architecture.summary.architecturePattern,
            }
          : { state: 'not_assessed', language: null, framework: null, architecturePattern: null },
        structure: architecture
          ? {
              state: 'assessed',
              totalModules: architecture.summary.totalModules,
              totalNodes: architecture.summary.totalNodes,
            }
          : { state: 'not_assessed', totalModules: null, totalNodes: null },
        dependencies: dependencies
          ? { state: 'assessed', totalDependencies: dependencies.totalDependencies }
          : { state: 'not_assessed', totalDependencies: null },
        headline: headline
          ? { state: 'assessed', message: headline.message, severity: headline.severity }
          : { state: 'not_assessed', message: null, severity: null },
        coverage: insights
          ? {
              state: 'assessed',
              extractorCount: insights.extractorSet.length,
              languageCount: insights.languages.length,
            }
          : { state: 'not_assessed', extractorCount: null, languageCount: null },
      });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [repository, repositoryId]);

  return summary;
}
