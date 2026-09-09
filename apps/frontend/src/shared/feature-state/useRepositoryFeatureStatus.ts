import type { FeatureStatus } from '@/shared/types';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export type RepositoryFeatureEmptyReason = 'no-completed-repositories' | 'no-active-repository' | null;

export function useRepositoryFeatureStatus() {
  const { activeRepository, completedRepositories } = useRepository();

  const status: FeatureStatus =
    completedRepositories.length === 0 || !activeRepository || activeRepository.status !== 'completed'
      ? 'empty'
      : 'success';

  const emptyReason: RepositoryFeatureEmptyReason =
    status === 'empty'
      ? completedRepositories.length === 0
        ? 'no-completed-repositories'
        : 'no-active-repository'
      : null;

  return {
    activeRepository,
    completedRepositories,
    status,
    loading: false,
    error: null,
    empty: status === 'empty',
    success: status === 'success',
    source: activeRepository?.source || null,
    emptyReason,
    retry: () => undefined,
    refresh: () => undefined,
  };
}
