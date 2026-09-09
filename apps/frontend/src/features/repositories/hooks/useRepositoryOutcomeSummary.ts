import { useEffect, useState } from 'react';
import type { Repository } from '@/shared/types';
import type { EngineeringReview, ReviewCategory } from '@/shared/types/review';
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
    /** The category the headline count is drawn from, so callers can link
     * straight to that filtered Review view. Null only when there is
     * nothing to point at (no findings at all). */
    categoryId: ReviewCategory | null;
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
  headline: { state: 'loading', message: null, categoryId: null },
  coverage: { state: 'loading', extractorCount: null, languageCount: null },
};

/**
 * Names the diagnostic category behind the count instead of borrowing
 * engineering-severity language for it (#335). `severity` on a finding comes
 * from the extractor's own diagnostic level (fatal/error/warning/info), not a
 * reviewed quality judgment -- a repository dominated by, say, unresolved
 * relationship diagnostics should not read as "N medium-severity findings",
 * which a user reasonably interprets as N graded code problems.
 */
function headlineFromReview(review: EngineeringReview): { message: string; categoryId: ReviewCategory | null } {
  const topCategory = [...review.categories]
    .filter((category) => category.findingCount > 0)
    .sort((a, b) => b.findingCount - a.findingCount)[0];

  if (!topCategory) {
    return { message: 'No evidence-backed findings were surfaced', categoryId: null };
  }

  const count = topCategory.findingCount;
  const label = topCategory.label.charAt(0).toLowerCase() + topCategory.label.slice(1);
  return {
    message: `${count} ${label} finding${count === 1 ? '' : 's'} — inspect coverage and filters`,
    categoryId: topCategory.id,
  };
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
          ? { state: 'assessed', message: headline.message, categoryId: headline.categoryId }
          : { state: 'not_assessed', message: null, categoryId: null },
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
