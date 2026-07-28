import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAIWorkspace } from './useAIWorkspace';
import { useRepositoryFeatureStatus } from '@/shared/feature-state/useRepositoryFeatureStatus';
import { aiService } from '@/shared/services/api';
import type { AiConversationResponse, AiQueryResponse } from '@/shared/services/api/types';
import type { Repository } from '@/shared/types';

vi.mock('@/shared/feature-state/useRepositoryFeatureStatus', () => ({
  useRepositoryFeatureStatus: vi.fn(),
}));

vi.mock('@/shared/services/api', () => ({
  aiService: {
    query: vi.fn(),
    getConfig: vi.fn().mockResolvedValue({ provider: 'anthropic', hasKey: true }),
    listConversations: vi.fn().mockResolvedValue({ repositoryId: 'repo-1', messages: [] }),
  },
  getErrorMessage: vi.fn((error: unknown) => String(error)),
}));

const repository: Repository = {
  id: 'repo-1',
  name: 'sample',
  source: 'upload',
  size: 0,
  fileCount: 0,
  status: 'completed',
  analysisStage: 'completed',
  analysisProgress: 100,
  uploadedAt: '2026-07-22T00:00:00Z',
  meta: null,
  fileTree: [],
};

describe('useAIWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRepositoryFeatureStatus).mockReturnValue({
      activeRepository: repository,
      completedRepositories: [repository],
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      source: 'upload',
      emptyReason: null,
      retry: vi.fn(),
      refresh: vi.fn(),
    });
  });

  it('uses the buffered query response instead of pseudo-streaming words', async () => {
    const response: AiQueryResponse = {
      message: {
        role: 'assistant',
        content: 'The answer is complete.',
        timestamp: '2026-07-22T00:00:01Z',
        citations: [],
      },
      suggestions: ['Ask a follow-up'],
    };
    vi.mocked(aiService.query).mockResolvedValue(response);

    const { result } = renderHook(() => useAIWorkspace());
    act(() => result.current.setQuery('Explain this repository.'));

    await act(async () => {
      await result.current.ask();
    });

    expect(aiService.query).toHaveBeenCalledWith({
      repositoryId: 'repo-1',
      query: 'Explain this repository.',
      context: { conversationHistory: [] },
    });
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1]).toEqual(response.message);
    expect(result.current.suggestions).toEqual(response.suggestions);
  });

  it('restores the persisted conversation thread on mount', async () => {
    const persisted: AiConversationResponse = {
      repositoryId: 'repo-1',
      messages: [
        { role: 'user', content: 'What does this repo do?', timestamp: '2026-07-22T00:00:00Z' },
        { role: 'assistant', content: 'It is a sample app.', timestamp: '2026-07-22T00:00:01Z', citations: [] },
      ],
    };
    vi.mocked(aiService.listConversations).mockResolvedValue(persisted);

    const { result } = renderHook(() => useAIWorkspace());

    await waitFor(() => expect(result.current.messages).toEqual(persisted.messages));
    expect(aiService.listConversations).toHaveBeenCalledWith('repo-1');
  });

  it('reloads the thread when the active repository changes', async () => {
    const firstThread: AiConversationResponse = {
      repositoryId: 'repo-1',
      messages: [{ role: 'user', content: 'About repo one', timestamp: '2026-07-22T00:00:00Z' }],
    };
    const secondRepository: Repository = { ...repository, id: 'repo-2', name: 'other' };
    const secondThread: AiConversationResponse = {
      repositoryId: 'repo-2',
      messages: [{ role: 'user', content: 'About repo two', timestamp: '2026-07-22T00:00:05Z' }],
    };
    vi.mocked(aiService.listConversations).mockImplementation((repositoryId: string) =>
      Promise.resolve(repositoryId === 'repo-1' ? firstThread : secondThread),
    );

    const { result, rerender } = renderHook(() => useAIWorkspace());
    await waitFor(() => expect(result.current.messages).toEqual(firstThread.messages));

    vi.mocked(useRepositoryFeatureStatus).mockReturnValue({
      activeRepository: secondRepository,
      completedRepositories: [secondRepository],
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      source: 'upload',
      emptyReason: null,
      retry: vi.fn(),
      refresh: vi.fn(),
    });
    rerender();

    await waitFor(() => expect(result.current.messages).toEqual(secondThread.messages));
    expect(aiService.listConversations).toHaveBeenCalledWith('repo-2');
  });

  it('surfaces a history load failure instead of rendering an empty thread', async () => {
    vi.mocked(aiService.listConversations).mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useAIWorkspace());

    await waitFor(() => expect(result.current.historyError).not.toBeNull());
    // The failure must be visible through the unified error channel too, so the
    // page renders an error state rather than the misleading empty state.
    expect(result.current.error).not.toBeNull();
    expect(result.current.messages).toHaveLength(0);
  });

  it('retryLoad clears the history error and reloads', async () => {
    vi.mocked(aiService.listConversations)
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce({ repositoryId: 'repo-1', messages: [] });

    const { result } = renderHook(() => useAIWorkspace());
    await waitFor(() => expect(result.current.historyError).not.toBeNull());

    act(() => result.current.retryLoad());
    await waitFor(() => expect(result.current.historyError).toBeNull());
    expect(aiService.listConversations).toHaveBeenCalledTimes(2);
  });

  it('discards a stale retried response when the active repository changes', async () => {
    // Repo A's response resolves late; meanwhile the user switches to an empty
    // repo B. The late A response must not install A's thread into B.
    let resolveA!: (value: unknown) => void;
    const aPending = new Promise((resolve) => {
      resolveA = resolve;
    });
    const secondRepository: Repository = { ...repository, id: 'repo-2', name: 'other' };

    vi.mocked(aiService.listConversations).mockImplementation((repositoryId: string) => {
      if (repositoryId === 'repo-1') return aPending as unknown as Promise<AiConversationResponse>;
      return Promise.resolve({ repositoryId: 'repo-2', messages: [] });
    });

    const { result, rerender } = renderHook(() => useAIWorkspace());
    // Trigger a retried load of repo-1 that stays pending.
    act(() => result.current.retryLoad());
    await waitFor(() => expect(aiService.listConversations).toHaveBeenCalledWith('repo-1'));

    // Switch to repo-2 (empty), then let the stale repo-1 response arrive.
    vi.mocked(useRepositoryFeatureStatus).mockReturnValue({
      activeRepository: secondRepository,
      completedRepositories: [secondRepository],
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      source: 'upload',
      emptyReason: null,
      retry: vi.fn(),
      refresh: vi.fn(),
    });
    rerender();
    await waitFor(() => expect(aiService.listConversations).toHaveBeenCalledWith('repo-2'));

    act(() => {
      resolveA({ repositoryId: 'repo-1', messages: [{ role: 'user', content: 'LEAK', timestamp: '2026-07-22T00:00:00Z' }] });
    });

    // The active repository is repo-2 (empty), so the stale repo-1 payload is
    // discarded and must never appear in messages.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current.messages).toHaveLength(0);
  });

  it('discards an in-flight assistant answer when the repository switches', async () => {
    // Ask on repo A; while the provider responds, switch to empty repo B.
    // A's assistant answer must not land in B's thread.
    let resolveQuery!: (value: unknown) => void;
    const queryPending = new Promise((resolve) => {
      resolveQuery = resolve;
    });
    const secondRepository: Repository = { ...repository, id: 'repo-2', name: 'other' };

    vi.mocked(aiService.query).mockReturnValue(queryPending as unknown as Promise<AiQueryResponse>);
    vi.mocked(aiService.listConversations).mockResolvedValue({ repositoryId: 'repo-2', messages: [] });

    const { result, rerender } = renderHook(() => useAIWorkspace());
    await waitFor(() => expect(result.current.messages).toHaveLength(0));

    act(() => result.current.setQuery('question for A'));
    // Fire ask without awaiting the (mocked-pending) provider response.
    act(() => {
      void result.current.ask();
    });
    // The optimistic user message for A is now shown.
    await waitFor(() => expect(result.current.messages).toHaveLength(1));

    // Switch to repo-2 (empty) while the query is still pending.
    vi.mocked(useRepositoryFeatureStatus).mockReturnValue({
      activeRepository: secondRepository,
      completedRepositories: [secondRepository],
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      source: 'upload',
      emptyReason: null,
      retry: vi.fn(),
      refresh: vi.fn(),
    });
    rerender();
    await waitFor(() => expect(aiService.listConversations).toHaveBeenCalledWith('repo-2'));

    // The late answer for repo A arrives; it must be discarded for repo B.
    act(() => {
      resolveQuery({
        message: { role: 'assistant', content: 'ANSWER FOR A', timestamp: '2026-07-22T00:00:05Z', citations: [] },
        suggestions: [],
      });
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current.messages).toHaveLength(0);
  });
});
