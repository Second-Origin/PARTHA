import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { backendService } from '@/shared/services/backend';
import type { RepositoryLineageResponse } from '@/shared/services/api/types';
import { RepositoryLineageHistory } from './RepositoryLineageHistory';

const standalone: RepositoryLineageResponse = {
  isLineaged: false,
  lineageId: null,
  canonicalSourceKey: null,
  canonicalBranch: null,
  entries: [
    {
      repositoryId: 'repo-1',
      sequence: null,
      name: 'sample',
      status: 'completed',
      revision: { kind: 'upload', value: `sha256:${'0'.repeat(64)}` },
      uploadedAt: '2026-07-22T08:00:00Z',
      isCurrent: true,
    },
  ],
};

const lineaged: RepositoryLineageResponse = {
  isLineaged: true,
  lineageId: 'lineage-1',
  canonicalSourceKey: 'github.com/acme/widgets',
  canonicalBranch: 'refs/heads/main',
  entries: [
    {
      repositoryId: 'repo-2',
      sequence: 2,
      name: 'widgets',
      status: 'completed',
      revision: { kind: 'git', value: 'b'.repeat(40), ref: 'refs/heads/main' },
      uploadedAt: '2026-08-01T00:00:00Z',
      isCurrent: true,
    },
    {
      repositoryId: 'repo-1',
      sequence: 1,
      name: 'widgets',
      status: 'completed',
      revision: { kind: 'git', value: 'a'.repeat(40), ref: 'refs/heads/main' },
      uploadedAt: '2026-07-01T00:00:00Z',
      isCurrent: false,
    },
  ],
};

describe('RepositoryLineageHistory', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a standalone import with an explanatory note and no link to another entry', async () => {
    vi.spyOn(backendService, 'fetchRepositoryLineage').mockResolvedValue(standalone);

    render(
      <MemoryRouter>
        <RepositoryLineageHistory repositoryId="repo-1" />
      </MemoryRouter>,
    );

    expect(await screen.findByText('sample')).toBeInTheDocument();
    expect(screen.getByText(/standalone import/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'View' })).not.toBeInTheDocument();
  });

  it('renders every lineage member, most recent first, with a link to every other one', async () => {
    vi.spyOn(backendService, 'fetchRepositoryLineage').mockResolvedValue(lineaged);

    render(
      <MemoryRouter>
        <RepositoryLineageHistory repositoryId="repo-2" />
      </MemoryRouter>,
    );

    await screen.findByText('#2');
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.queryByText(/standalone import/)).not.toBeInTheDocument();

    const link = screen.getByRole('link', { name: 'View' });
    expect(link).toHaveAttribute('href', '/repositories/repo-1');
  });

  it('renders an honest error state with a retry action on failure', async () => {
    vi.spyOn(backendService, 'fetchRepositoryLineage').mockRejectedValue(new Error('network down'));

    render(
      <MemoryRouter>
        <RepositoryLineageHistory repositoryId="repo-1" />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Couldn't load history")).toBeInTheDocument());
    expect(screen.getByText('network down')).toBeInTheDocument();
  });
});
