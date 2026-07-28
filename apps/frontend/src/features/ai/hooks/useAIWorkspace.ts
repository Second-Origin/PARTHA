import { useCallback, useEffect, useRef, useState } from 'react';
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
  const [historyError, setHistoryError] = useState<string | null>(null);
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

  // Tracks the currently active repository id so in-flight requests can check
  // (at resolution time, not call time) whether their repository is still the
  // one being viewed. The ask/load closures capture a stale repositoryFeature,
  // so they must read this ref instead.
  const activeRepoIdRef = useRef(repositoryFeature.activeRepository?.id);

  // Monotonic token for the most recent history load. Every loadHistory call
  // bumps it; a response whose captured token no longer matches is stale and
  // must be discarded. This is what keeps a retried load (whose cleanup is
  // dropped by callers) from installing another repository's thread after the
  // active repository has changed.
  const loadSeq = useRef(0);

  // Monotonic token for queries. A query whose token no longer matches the
  // latest ask is stale and must not mutate state (e.g. the user asked again,
  // or switched repositories while the provider was responding).
  const askSeq = useRef(0);

  const loadHistory = useCallback((repositoryId: string | undefined) => {
    setMessages([]);
    setHistoryError(null);
    if (!repositoryId) return;

    const seq = ++loadSeq.current;
    aiService
      .listConversations(repositoryId)
      .then((response) => {
        // Discard if a newer load started (e.g. a retry, or a repository
        // switch) or if the response is for a different repository than the
        // one we asked about.
        if (seq !== loadSeq.current) return;
        if (response.repositoryId !== repositoryId) return;
        // If the user has already asked a question before this load
        // resolved, keep the in-progress thread instead of overwriting it.
        setMessages((current) => (current.length === 0 ? response.messages : current));
      })
      .catch((caught) => {
        if (seq !== loadSeq.current) return;
        // A transient network/server failure must not look like lost
        // history: surface it so the UI shows an error + retry rather than
        // the empty state.
        setHistoryError(getErrorMessage(caught));
      });
  }, []);

  useEffect(() => {
    activeRepoIdRef.current = repositoryFeature.activeRepository?.id;
    loadHistory(repositoryFeature.activeRepository?.id);
  }, [repositoryFeature.activeRepository?.id, loadHistory]);

  const ask = useCallback(async () => {
    const activeRepository = repositoryFeature.activeRepository;
    const trimmed = query.trim();
    if (!activeRepository || !trimmed) return;

    const requestedId = activeRepository.id;
    const seq = ++askSeq.current;

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
        repositoryId: requestedId,
        query: trimmed,
        context: { conversationHistory: messages.slice(-8) },
      });
      // Discard if a newer ask started (e.g. asking again) or the user switched
      // away from the repository this answer belongs to. A late answer for repo
      // A must never land in repo B's thread.
      if (seq !== askSeq.current) return;
      if (activeRepoIdRef.current !== requestedId) return;
      setMessages((current) => [...current, response.message]);
      setSuggestions(response.suggestions || []);
    } catch (caught) {
      if (seq !== askSeq.current) return;
      if (activeRepoIdRef.current !== requestedId) return;
      setError(getErrorMessage(caught));
    } finally {
      if (seq === askSeq.current) setLoading(false);
    }
  }, [messages, query, repositoryFeature.activeRepository]);

  return {
    ...repositoryFeature,
    query,
    setQuery,
    messages,
    suggestions,
    loading: repositoryFeature.loading || loading,
    error: repositoryFeature.error || error || historyError,
    historyError,
    retryLoad: () => loadHistory(repositoryFeature.activeRepository?.id),
    providerConfigured,
    ask,
  };
}
