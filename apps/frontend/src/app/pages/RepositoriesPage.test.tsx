import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Repository } from '@/shared/types';
import { useRepository } from '@/features/repositories/hooks/useRepository';
import { RepositoriesPage } from './RepositoriesPage';

const navigateMock = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigateMock };
});

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: vi.fn(),
}));

const repository: Repository = {
  id: 'repo-1',
  name: 'kalyx',
  source: 'github',
  size: 10,
  fileCount: 5,
  status: 'completed',
  analysisStage: 'completed',
  analysisProgress: 100,
  uploadedAt: '2026-08-02T08:00:00Z',
  meta: {
    language: 'TypeScript',
    framework: 'React',
    totalFiles: 5,
    totalFolders: 2,
    entryPoint: 'src/main.tsx',
    configFiles: [],
    packageManager: 'npm',
    hasReadme: true,
    hasLicense: true,
    licenseName: 'MIT',
  },
  fileTree: [],
};

function mockUseRepository(overrides: Partial<ReturnType<typeof useRepository>>) {
  vi.mocked(useRepository).mockReturnValue({
    repositories: [],
    removeRepository: vi.fn(),
    selectRepository: vi.fn(),
    loading: false,
    error: null,
    retry: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useRepository>);
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RepositoriesPage />
    </MemoryRouter>,
  );
}

describe('RepositoriesPage', () => {
  beforeEach(() => {
    navigateMock.mockClear();
  });

  it('shows a loading state while repositories are being fetched', () => {
    mockUseRepository({ loading: true });

    renderPage();

    expect(screen.getByText('Loading repositories...')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows an honest empty state for an authenticated user with no repositories, not a fabricated table', () => {
    mockUseRepository({ repositories: [] });

    renderPage();

    expect(screen.getByText('No repositories yet')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Upload Repository' }));
    expect(navigateMock).toHaveBeenCalledWith('/upload');
  });

  it('shows a truthful, actionable error message with a working retry, not the table', async () => {
    const retry = vi.fn();
    mockUseRepository({ error: 'The repository service is unavailable.', retry });

    renderPage();

    expect(screen.getByText('Unable to load repositories')).toBeInTheDocument();
    expect(screen.getByText('The repository service is unavailable.')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(retry).toHaveBeenCalledTimes(1));
  });

  it('renders a populated repository list with its real data, not placeholder values', () => {
    mockUseRepository({ repositories: [repository] });

    renderPage();

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('kalyx')).toBeInTheDocument();
    expect(screen.getByText('GitHub')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('names row actions with repository context and hides their decorative icons', () => {
    mockUseRepository({ repositories: [repository] });

    renderPage();

    const open = screen.getByRole('button', { name: 'Open kalyx' });
    const remove = screen.getByRole('button', { name: 'Delete kalyx' });

    expect(open.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(remove.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('opening a completed repository selects it and navigates to its detail page', () => {
    const selectRepository = vi.fn();
    mockUseRepository({ repositories: [repository], selectRepository });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'Open kalyx' }));

    expect(selectRepository).toHaveBeenCalledWith(repository);
    expect(navigateMock).toHaveBeenCalledWith('/repositories/repo-1');
  });

  it('opening an in-progress repository navigates to its analysis progress page instead', () => {
    const analysing: Repository = { ...repository, status: 'analysing' };
    mockUseRepository({ repositories: [analysing] });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'Open kalyx' }));

    expect(navigateMock).toHaveBeenCalledWith('/analysis/repo-1');
  });

  it('deleting a repository calls removeRepository and surfaces a truthful error on failure', async () => {
    const removeRepository = vi.fn().mockRejectedValue(new Error('Repository is still analysing.'));
    mockUseRepository({ repositories: [repository], removeRepository });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'Delete kalyx' }));

    expect(removeRepository).toHaveBeenCalledWith('repo-1');
    expect(await screen.findByText('Repository is still analysing.')).toBeInTheDocument();
  });
});
