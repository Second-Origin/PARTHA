import { useCallback } from 'react';
import type { Repository } from '@/shared/types';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepositoryContext } from '../context/repository-context';

export function useRepository() {
  const context = useRepositoryContext();
  const removeFromStore = useAppStore((state) => state.removeRepository);

  const selectRepository = useCallback(
    (repository: Repository | string | null) => {
      const id = typeof repository === 'string' ? repository : repository?.id || null;
      context.setActiveRepositoryId(id);
    },
    [context],
  );

  const removeRepository = useCallback(
    async (id: string) => {
      try {
        const removed = await backendService.deleteRepository(id);
        if (removed) removeFromStore(id);
      } catch (caught) {
        const error = new Error(getErrorMessage(caught)) as Error & { cause?: unknown };
        error.cause = caught;
        throw error;
      }
    },
    [removeFromStore],
  );

  return {
    ...context,
    selectRepository,
    removeRepository,
    empty: context.repositories.length === 0,
    success: context.repositories.length > 0,
    loading: context.loading,
    error: context.error,
    retry: context.refresh,
    refresh: context.refresh,
  };
}
