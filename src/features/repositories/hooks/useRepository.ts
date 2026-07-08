import { useCallback } from 'react';
import type { Repository } from '@/types';
import { backendService } from '@/services/backend';
import { useAppStore } from '@/store/useAppStore';
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
      const removed = await backendService.deleteRepository(id);
      if (removed) removeFromStore(id);
    },
    [removeFromStore],
  );

  return {
    ...context,
    selectRepository,
    removeRepository,
    empty: context.repositories.length === 0,
    success: context.repositories.length > 0,
    loading: false,
    error: null,
    retry: () => undefined,
    refresh: () => undefined,
  };
}
