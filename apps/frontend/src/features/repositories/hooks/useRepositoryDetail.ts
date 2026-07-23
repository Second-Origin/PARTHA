import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useRepository } from './useRepository';

const tabs = ['Overview', 'Explorer'] as const;
export type RepositoryDetailTab = (typeof tabs)[number];

function isRepositoryDetailTab(value: string | null): value is RepositoryDetailTab {
  return (tabs as readonly string[]).includes(value ?? '');
}

export function useRepositoryDetail(repositoryId: string | undefined) {
  const repositoryState = useRepository();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<RepositoryDetailTab>(
    isRepositoryDetailTab(searchParams.get('tab')) ? (searchParams.get('tab') as RepositoryDetailTab) : 'Overview',
  );

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
