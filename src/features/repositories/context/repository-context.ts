import { createContext, useContext } from 'react';
import type { Repository } from '@/types';

export interface RepositoryContextValue {
  repositories: Repository[];
  activeRepository: Repository | null;
  activeRepositoryId: string | null;
  completedRepositories: Repository[];
  hasRepositories: boolean;
  setActiveRepositoryId: (id: string | null) => void;
}

export const RepositoryContext = createContext<RepositoryContextValue | null>(null);

export function useRepositoryContext() {
  const context = useContext(RepositoryContext);
  if (!context) {
    throw new Error('useRepositoryContext must be used within RepositoryProvider');
  }
  return context;
}
