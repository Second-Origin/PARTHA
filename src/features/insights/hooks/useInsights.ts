import { useRepositoryFeatureStatus } from '@/features/shared/useRepositoryFeatureStatus';

export function useInsights() {
  return useRepositoryFeatureStatus();
}
