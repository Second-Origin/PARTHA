import { useCallback, useEffect, useState } from 'react';
import type { FeatureStatus } from '@/shared/types';
import type { AuthenticationExplanationResponse } from '@/shared/services/api/types';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export function useAuthenticationExplanation(enabled: boolean) {
  const { activeRepository } = useRepository();
  const [explanation, setExplanation] = useState<AuthenticationExplanationResponse | null>(null);
  const [status, setStatus] = useState<FeatureStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);

  useEffect(() => {
    if (!enabled) return;

    if (!activeRepository || activeRepository.status !== 'completed') {
      setStatus('empty');
      setExplanation(null);
      setError(null);
      return;
    }

    let cancelled = false;

    async function load() {
      if (!activeRepository) return;
      setStatus('loading');
      setError(null);

      try {
        const response = await backendService.fetchAuthenticationExplanation(activeRepository);
        if (cancelled) return;
        setExplanation(response);
        setStatus('success');
      } catch (caught) {
        if (cancelled) return;
        setExplanation(null);
        setError(getErrorMessage(caught));
        setStatus('error');
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [activeRepository, enabled, refreshKey]);

  return {
    explanation,
    status,
    loading: status === 'loading',
    error,
    empty: status === 'empty',
    success: status === 'success',
    retry: refresh,
  };
}
