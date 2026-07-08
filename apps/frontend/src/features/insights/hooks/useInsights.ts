import { useRepositoryFeatureStatus } from '@/shared/feature-state/useRepositoryFeatureStatus';

export function useInsights() {
  return useRepositoryFeatureStatus();
}
