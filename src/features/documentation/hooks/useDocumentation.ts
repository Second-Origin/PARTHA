import { useCallback, useEffect, useState } from 'react';
import { documentationService, getErrorMessage } from '@/services/api';
import type { GenerateDocResponse } from '@/services/api/types';
import { useRepositoryFeatureStatus } from '@/features/shared/useRepositoryFeatureStatus';

export function useDocumentation() {
  const state = useRepositoryFeatureStatus();
  const [document, setDocument] = useState<GenerateDocResponse | null>(null);
  const [sections, setSections] = useState<string[]>([
    'overview',
    'architecture',
    'folder-structure',
    'api',
    'environment',
    'deployment',
    'contribution',
  ]);
  const [format, setFormat] = useState<'markdown' | 'html'>('markdown');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => {
    setError(null);
    setRefreshKey((key) => key + 1);
  }, []);

  const toggleSection = useCallback((section: string) => {
    setSections((current) =>
      current.includes(section)
        ? current.filter((item) => item !== section)
        : [...current, section],
    );
  }, []);

  useEffect(() => {
    if (!state.activeRepository || state.activeRepository.status !== 'completed') {
      setDocument(null);
      setError(null);
      return;
    }

    let cancelled = false;
    async function generate() {
      if (!state.activeRepository) return;
      setLoading(true);
      setError(null);
      try {
        const nextDocument = await documentationService.generate({
          repositoryId: state.activeRepository.id,
          format,
          sections,
        });
        if (!cancelled) setDocument(nextDocument);
      } catch (caught) {
        if (!cancelled) setError(getErrorMessage(caught));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void generate();
    return () => {
      cancelled = true;
    };
  }, [format, refreshKey, sections, state.activeRepository]);

  return {
    ...state,
    document,
    sections,
    format,
    setFormat,
    toggleSection,
    loading: state.loading || loading,
    error: state.error || error,
    retry: refresh,
    refresh,
  };
}
