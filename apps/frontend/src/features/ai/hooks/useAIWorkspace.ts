import { useCallback, useEffect, useState } from 'react';
import { aiService, getErrorMessage } from '@/shared/services/api';
import type { AiMessage } from '@/shared/services/api/types';
import { useRepositoryFeatureStatus } from '@/shared/feature-state/useRepositoryFeatureStatus';

export function useAIWorkspace() {
  const repositoryFeature = useRepositoryFeatureStatus();
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerConfigured, setProviderConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    aiService
      .getConfig()
      .then(() => !cancelled && setProviderConfigured(true))
      .catch(() => !cancelled && setProviderConfigured(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const ask = useCallback(async () => {
    const activeRepository = repositoryFeature.activeRepository;
    const trimmed = query.trim();
    if (!activeRepository || !trimmed) return;

    const userMessage: AiMessage = {
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    };

    setMessages((current) => [...current, userMessage]);
    setQuery('');
    setLoading(true);
    setError(null);

    try {
      const response = await aiService.query({
        repositoryId: activeRepository.id,
        query: trimmed,
        context: { conversationHistory: messages.slice(-8) },
      });
      setMessages((current) => [...current, response.message]);
      setSuggestions(response.suggestions || []);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [messages, query, repositoryFeature.activeRepository]);

  return {
    ...repositoryFeature,
    query,
    setQuery,
    messages,
    suggestions,
    loading: repositoryFeature.loading || loading,
    error: repositoryFeature.error || error,
    providerConfigured,
    ask,
  };
}
