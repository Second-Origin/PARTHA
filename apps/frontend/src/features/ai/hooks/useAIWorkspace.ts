import { useCallback, useState } from 'react';
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
      const assistantTimestamp = new Date().toISOString();
      const assistantMessage: AiMessage = {
        role: 'assistant',
        content: '',
        timestamp: assistantTimestamp,
        citations: [],
      };
      setMessages((current) => [...current, assistantMessage]);

      await aiService.streamQuery({
        repositoryId: activeRepository.id,
        query: trimmed,
        context: { conversationHistory: messages.slice(-8) },
      }, (chunk) => {
        if (chunk.type === 'content' && chunk.content) {
          setMessages((current) =>
            current.map((message) =>
              message.timestamp === assistantTimestamp
                ? { ...message, content: `${message.content}${chunk.content}` }
                : message,
            ),
          );
        }
        if (chunk.type === 'citation' && chunk.citation) {
          setMessages((current) =>
            current.map((message) =>
              message.timestamp === assistantTimestamp
                ? { ...message, citations: [...(message.citations || []), chunk.citation!] }
                : message,
            ),
          );
        }
        if (chunk.type === 'error' && chunk.error) {
          setError(chunk.error);
        }
      });
      setSuggestions([
        'Explain the main architecture boundaries.',
        'What files should I read first?',
        'What are the highest-risk engineering issues?',
      ]);
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
    ask,
  };
}
