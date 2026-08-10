import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AIWorkspacePage } from './AIWorkspacePage';

vi.mock('@/features/ai/hooks/useAIWorkspace', () => ({
  useAIWorkspace: () => ({
    activeRepository: { id: 'repo-1', name: 'partha', source: 'upload' },
    source: 'upload', emptyReason: null, query: '', setQuery: vi.fn(),
    messages: [], suggestions: [], loading: false, error: null,
    historyError: false, providerConfigured: false, ask: vi.fn(), retryLoad: vi.fn(),
  }),
}));

describe('AIWorkspacePage composer', () => {
  it('keeps the real provider setup state and question composer available', () => {
    render(<MemoryRouter><AIWorkspacePage /></MemoryRouter>);

    expect(screen.getByRole('heading', { name: 'AI Workspace' })).toBeVisible();
    expect(screen.getByText(/No AI provider is configured/)).toBeVisible();
    expect(screen.getByLabelText('Ask about the codebase')).toBeVisible();
    expect(screen.getByRole('button', { name: /Settings/i })).toBeVisible();
  });
});
