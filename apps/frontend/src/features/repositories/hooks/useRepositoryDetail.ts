import { useMemo, useState } from 'react';
import { useRepository } from './useRepository';

const tabs = ['Overview', 'Explorer'] as const;
export type RepositoryDetailTab = (typeof tabs)[number];

export function useRepositoryDetail(repositoryId: string | undefined) {
  const repositoryState = useRepository();
  const [activeTab, setActiveTab] = useState<RepositoryDetailTab>('Overview');

  const repository = useMemo(
    () => repositoryState.repositories.find((repo) => repo.id === repositoryId) || null,
    [repositoryId, repositoryState.repositories],
  );

  return {
    ...repositoryState,
    repository,
    tabs,
    activeTab,
    setActiveTab,
    notFound: !repository,
    redirectToAnalysis:
      repository?.status === 'analysing' || repository?.status === 'cancelled'
        ? `/analysis/${repository.id}`
        : null,
  };
}
