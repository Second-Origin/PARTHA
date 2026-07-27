import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDocumentation } from '@/features/documentation/hooks/useDocumentation';
import { DocumentationPage } from './DocumentationPage';

vi.mock('@/features/documentation/hooks/useDocumentation', () => ({
  useDocumentation: vi.fn(),
}));

const activeRepository = {
  id: 'repo-1',
  name: 'sample',
  source: 'upload' as const,
  size: 100,
  fileCount: 2,
  status: 'completed' as const,
  analysisStage: 'completed' as const,
  analysisProgress: 100,
  uploadedAt: '2026-07-15T00:00:00Z',
  meta: null,
  fileTree: [],
};

const base: ReturnType<typeof useDocumentation> = {
  activeRepository,
  completedRepositories: [activeRepository],
  status: 'success',
  loading: false,
  error: null,
  noSnapshot: false,
  empty: false,
  success: true,
  source: 'upload',
  emptyReason: null,
  document: {
    content: '# sample\n',
    format: 'markdown',
    generatedAt: '2026-07-25T00:00:00Z',
    source: 'ri.v1',
    snapshotId: 'snap_example',
    snapshotSchemaVersion: 'ri.v1',
    revisionKind: 'upload',
    revisionValue: `sha256:${'0'.repeat(64)}`,
  },
  sections: ['overview'],
  format: 'markdown',
  setFormat: vi.fn(),
  toggleSection: vi.fn(),
  retry: vi.fn(),
  refresh: vi.fn(),
};

function renderPage() {
  return render(
    <MemoryRouter>
      <DocumentationPage />
    </MemoryRouter>,
  );
}

function mockDocumentation(overrides: Partial<typeof base> = {}) {
  vi.mocked(useDocumentation).mockReturnValue({ ...base, ...overrides });
}

describe('DocumentationPage', () => {
  beforeEach(() => {
    mockDocumentation();
  });

  it('renders the generated document for a successful load', () => {
    renderPage();

    expect(screen.getByText('snap_example', { exact: false })).toBeInTheDocument();
  });

  it('guides the user to run analysis again instead of showing a generic error when no sealed snapshot exists (#178)', () => {
    mockDocumentation({ document: null, success: false, noSnapshot: true });

    renderPage();

    expect(screen.getByText('No sealed snapshot yet')).toBeInTheDocument();
    expect(
      screen.getByText(
        'This repository has no sealed Repository Intelligence snapshot for its current revision. Analyse it again to generate one.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run analysis/i })).toBeInTheDocument();
  });

  it('keeps a genuine error distinct from the no-snapshot state', () => {
    mockDocumentation({ document: null, success: false, error: 'Documentation service is unavailable.' });

    renderPage();

    expect(screen.getByText('Documentation service is unavailable.')).toBeInTheDocument();
    expect(screen.queryByText('No sealed snapshot yet')).not.toBeInTheDocument();
  });
});
