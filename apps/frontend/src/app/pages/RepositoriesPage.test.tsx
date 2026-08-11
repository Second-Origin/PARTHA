import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { Repository } from '@/shared/types';
import { RepositoriesPage } from './RepositoriesPage';

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

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({
    repositories: [repository],
    removeRepository: vi.fn(),
    selectRepository: vi.fn(),
    loading: false,
    error: null,
    retry: vi.fn(),
  }),
}));

describe('RepositoriesPage', () => {
  it('names row actions with repository context and hides their decorative icons', () => {
    render(
      <MemoryRouter>
        <RepositoriesPage />
      </MemoryRouter>,
    );

    const open = screen.getByRole('button', { name: 'Open kalyx' });
    const remove = screen.getByRole('button', { name: 'Delete kalyx' });

    expect(open.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(remove.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });
});
