import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAIWorkspace } from './useAIWorkspace';
import { useRepositoryFeatureStatus } from '@/shared/feature-state/useRepositoryFeatureStatus';
import { aiService } from '@/shared/services/api';
import type { AiQueryResponse } from '@/shared/services/api/types';
import type { Repository } from '@/shared/types';

vi.mock('@/shared/feature-state/useRepositoryFeatureStatus', () => ({
  useRepositoryFeatureStatus: vi.fn(),
}));

vi.mock('@/shared/services/api', () => ({
  aiService: {
    query: vi.fn(),
    streamQuery: vi.fn(),
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
    expect(aiService.streamQuery).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1]).toEqual(response.message);
    expect(result.current.suggestions).toEqual(response.suggestions);
  });
});
