import type { Repository } from '@/shared/types';

export function useRepositoryTree(repository: Repository | null) {
  const hasTree = Boolean(repository?.fileTree.length);

  return {
    repository,
    fileTree: repository?.fileTree || [],
    meta: repository?.meta || null,
    loading: false,
    error: null,
    empty: !hasTree,
    success: hasTree,
    retry: () => undefined,
    refresh: () => undefined,
    source: repository?.source || null,
  };
}
