import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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
        evidence: [{ snapshotId: 'snap_1', factId: 'src/dependencies.py::get_current_user', path: 'src/dependencies.py', startLine: 6, endLine: 7 }],
      },
      {
        kind: 'service',
        name: 'UserService',
        confidence: 'heuristic',
        evidence: [{ snapshotId: 'snap_1', factId: 'src/services.py::UserService', path: 'src/services.py', startLine: 3, endLine: 4 }],
      },
    ],
    relationships: [
      {
        subject: '/me',
        subjectKind: 'route',
        predicate: 'routes_to',
        object: 'read_me',
        objectKind: 'handler',
        evidence: [{ snapshotId: 'snap_1', factId: 'edge:1', path: 'src/routes.py', startLine: 19, endLine: 20 }],
      },
      {
        subject: 'read_me',
        subjectKind: 'handler',
        predicate: 'injects',
        object: 'get_current_user',
        objectKind: 'middleware',
        evidence: [{ snapshotId: 'snap_1', factId: 'edge:2', path: 'src/routes.py', startLine: 20, endLine: 20 }],
      },
      {
        subject: 'get_current_user',
        subjectKind: 'middleware',
        predicate: 'calls',
        object: 'UserService',
        objectKind: 'service',
        evidence: [{ snapshotId: 'snap_1', factId: 'edge:3', path: 'src/dependencies.py', startLine: 7, endLine: 7 }],
      },
    ],
    chains: [
      {
        route: '/me',
        hops: [
          {
            subject: '/me',
            subjectKind: 'route',
            predicate: 'routes_to',
            object: 'read_me',
            objectKind: 'handler',
            evidence: [{ snapshotId: 'snap_1', factId: 'edge:1', path: 'src/routes.py', startLine: 19, endLine: 20 }],
          },
          {
            subject: 'read_me',
            subjectKind: 'handler',
            predicate: 'injects',
            object: 'get_current_user',
            objectKind: 'middleware',
            evidence: [{ snapshotId: 'snap_1', factId: 'edge:2', path: 'src/routes.py', startLine: 20, endLine: 20 }],
          },
          {
            subject: 'get_current_user',
            subjectKind: 'middleware',
            predicate: 'calls',
            object: 'UserService',
            objectKind: 'service',
            evidence: [{ snapshotId: 'snap_1', factId: 'edge:3', path: 'src/dependencies.py', startLine: 7, endLine: 7 }],
          },
        ],
      },
    ],
    diagnostics: [],
    ...overrides,
  };
}

function renderPanel(open: boolean, onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <AuthenticationExplanationPanel open={open} onClose={onClose} />
    </MemoryRouter>,
  );
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

    renderPanel(false);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders the route -> handler -> guard -> service flow with grouped claims', () => {
    mockedUseAuthenticationExplanation.mockReturnValue({
      explanation: readyExplanation(),
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      retry: vi.fn(),
    });

    renderPanel(true);

    expect(screen.getByRole('dialog', { name: 'Authentication explanation' })).toBeInTheDocument();
    expect(screen.getByText('How authentication works')).toBeInTheDocument();
    expect(screen.getByText('Routes')).toBeInTheDocument();
    expect(screen.getByText('Middleware & guards')).toBeInTheDocument();
    expect(screen.getByText('Services')).toBeInTheDocument();

    // The chain shows every hop: route -> handler, handler -> guard, guard -> service.
    expect(screen.getAllByText('/me').length).toBeGreaterThan(0);
    expect(screen.getAllByText('read_me').length).toBeGreaterThan(0);
    expect(screen.getAllByText('get_current_user').length).toBeGreaterThan(0);
    expect(screen.getAllByText('UserService').length).toBeGreaterThan(0);
    expect(screen.getByText('routes_to')).toBeInTheDocument();
    expect(screen.getByText('injects')).toBeInTheDocument();
    expect(screen.getByText('calls')).toBeInTheDocument();
  });

  it('renders every evidence citation as a real, keyboard-accessible link to the exact snapshot/path/line', () => {
    mockedUseAuthenticationExplanation.mockReturnValue({
      explanation: readyExplanation(),
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      retry: vi.fn(),
    });

    renderPanel(true);

    const citation = screen.getByRole('link', { name: 'View evidence at src/dependencies.py, line 6-7' });
    expect(citation).toBeInTheDocument();
    expect(citation.tagName).toBe('A');
    // A real <a> is natively keyboard-focusable and activates on Enter -- no
    // onClick-only handler standing in for navigation.
    expect(citation).toHaveAttribute('href');
    const href = citation.getAttribute('href') ?? '';
    const url = new URL(href, 'http://localhost');
    expect(url.pathname).toBe('/repositories/repo-1');
    expect(url.searchParams.get('path')).toBe('src/dependencies.py');
    expect(url.searchParams.get('startLine')).toBe('6');
    expect(url.searchParams.get('endLine')).toBe('7');
    expect(url.searchParams.get('snapshotId')).toBe('snap_1');
    expect(url.searchParams.get('factId')).toBe('src/dependencies.py::get_current_user');
    expect(url.searchParams.get('tab')).toBe('Explorer');

    // The relationship (chain hop) citations are real links too, not just claim citations.
    const relationshipCitation = screen.getByRole('link', { name: 'View evidence at src/routes.py, line 19-20' });
    const relationshipHref = new URL(relationshipCitation.getAttribute('href') ?? '', 'http://localhost');
    expect(relationshipHref.searchParams.get('startLine')).toBe('19');
    expect(relationshipHref.searchParams.get('endLine')).toBe('20');
  });

  it('reports a missing snapshot honestly instead of an empty result', () => {
    mockedUseAuthenticationExplanation.mockReturnValue({
      explanation: readyExplanation({
        status: 'missing_snapshot',
        snapshotId: null,
        claims: [],
        relationships: [],
        chains: [],
        summary: 'No sealed repository intelligence snapshot is available for this repository yet.',
      }),
      status: 'success',
      loading: false,
      error: null,
      empty: false,
      success: true,
      retry: vi.fn(),
    });

    renderPanel(true);
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

    renderPanel(true);
    screen.getByText('Retry').click();
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
