import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AuthenticationExplanationResponse } from '@/shared/services/api/types';
import { useAuthenticationExplanation } from '../hooks/useAuthenticationExplanation';
import { AuthenticationExplanationPanel } from './AuthenticationExplanationPanel';

vi.mock('../hooks/useAuthenticationExplanation');

const mockedUseAuthenticationExplanation = vi.mocked(useAuthenticationExplanation);

function readyExplanation(overrides: Partial<AuthenticationExplanationResponse> = {}): AuthenticationExplanationResponse {
  return {
    schemaVersion: 'auth-explanation.v1',
    repositoryId: 'repo-1',
    repositoryName: 'fixture',
    revisionKind: 'upload',
    revisionValue: 'sha256:0',
    snapshotId: 'snap_1',
    status: 'ready',
    summary: 'Found 1 authentication-relevant route(s).',
    claims: [
      {
        kind: 'route',
        name: '/me',
        confidence: 'observed',
        evidence: [{ snapshotId: 'snap_1', factId: 'src/routes.py::(anonymous:route#1)', path: 'src/routes.py', startLine: 19, endLine: 19 }],
      },
      {
        kind: 'middleware',
        name: 'get_current_user',
        confidence: 'heuristic',
        evidence: [{ snapshotId: 'snap_1', factId: 'src/service.py::get_current_user', path: 'src/service.py', startLine: 6, endLine: 7 }],
      },
    ],
    relationships: [],
    diagnostics: [],
    ...overrides,
  };
}

describe('AuthenticationExplanationPanel', () => {
  it('renders nothing when closed', () => {
    mockedUseAuthenticationExplanation.mockReturnValue({
      explanation: null,
      status: 'idle',
      loading: false,
      error: null,
      empty: false,
      success: false,
      retry: vi.fn(),
    });

    render(<AuthenticationExplanationPanel open={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows grouped claims with keyboard-accessible evidence citations', () => {
    mockedUseAuthenticationExplanation.mockReturnValue({
      explanation: readyExplanation(),
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      retry: vi.fn(),
    });

    render(<AuthenticationExplanationPanel open onClose={vi.fn()} />);

    expect(screen.getByRole('dialog', { name: 'Authentication explanation' })).toBeInTheDocument();
    expect(screen.getByText('Routes')).toBeInTheDocument();
    expect(screen.getByText('Middleware & guards')).toBeInTheDocument();

    const citation = screen.getByRole('button', { name: 'View evidence at src/service.py, line 6-7' });
    expect(citation).toBeInTheDocument();
    fireEvent.click(citation);
    expect(screen.getByText(/fact src\/service\.py::get_current_user/)).toBeInTheDocument();
  });

  it('reports a missing snapshot honestly instead of an empty result', () => {
    mockedUseAuthenticationExplanation.mockReturnValue({
      explanation: readyExplanation({
        status: 'missing_snapshot',
        snapshotId: null,
        claims: [],
        summary: 'No sealed repository intelligence snapshot is available for this repository yet.',
      }),
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      retry: vi.fn(),
    });

    render(<AuthenticationExplanationPanel open onClose={vi.fn()} />);
    expect(
      screen.getByText('No sealed repository intelligence snapshot is available for this repository yet.'),
    ).toBeInTheDocument();
  });

  it('offers a retry action on error', () => {
    const retry = vi.fn();
    mockedUseAuthenticationExplanation.mockReturnValue({
      explanation: null,
      status: 'error',
      loading: false,
      error: 'Request failed',
      empty: false,
      success: false,
      retry,
    });

    render(<AuthenticationExplanationPanel open onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Retry'));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
