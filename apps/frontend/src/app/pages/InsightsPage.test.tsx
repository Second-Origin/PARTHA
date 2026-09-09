import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useInsights } from '@/features/insights/hooks/useInsights';
import type { RepositoryInsights } from '@/shared/types/insights';
import { InsightsPage } from './InsightsPage';

vi.mock('@/features/insights/hooks/useInsights', () => ({
  useInsights: vi.fn(),
}));

const insightsData: RepositoryInsights = {
  schemaVersion: 'repository-insights.v1',
  repositoryId: 'repo-1',
  repositoryName: 'sample',
  revisionKind: 'upload',
  revisionValue: `sha256:${'0'.repeat(64)}`,
  snapshotId: 'snap_example',
  snapshotSchemaVersion: 'ri.v1',
  canonicalGraphHash: `sha256:${'1'.repeat(64)}`,
  manifestDigest: `sha256:${'2'.repeat(64)}`,
  provenance: {
    source: 'ri.v1',
    snapshotId: 'snap_example',
    snapshotSchemaVersion: 'ri.v1',
    canonicalGraphHash: `sha256:${'1'.repeat(64)}`,
  },
  computedAt: '2026-07-25T00:00:00Z',
  snapshotCreatedAt: '2026-07-25T00:00:00Z',
  snapshotSealedAt: '2026-07-25T00:00:05Z',
  extractorSet: [],
  metrics: [],
  relationshipsByPredicate: [],
  diagnosticsBySeverity: [],
  diagnosticsByCode: [],
  languages: [],
  changeOverTime: { assessmentState: 'not_assessed', message: 'Change-over-time insights are not available yet.' },
};

const base: ReturnType<typeof useInsights> = {
  data: insightsData,
  activeRepository: null,
  completedRepositories: [],
  status: 'success',
  loading: false,
  error: null,
  noSnapshot: false,
  empty: false,
  success: true,
  emptyReason: null,
  retry: vi.fn(),
  refresh: vi.fn(),
};

function renderPage() {
  return render(
    <MemoryRouter>
      <InsightsPage />
    </MemoryRouter>,
  );
}

function mockInsights(overrides: Partial<typeof base> = {}) {
  vi.mocked(useInsights).mockReturnValue({ ...base, ...overrides });
}

describe('InsightsPage', () => {
  beforeEach(() => {
    mockInsights();
  });

  it('renders the sealed snapshot identity for a successful load', () => {
    renderPage();

    expect(screen.getByText('snap_example')).toBeInTheDocument();
    expect(screen.getByText('Extractor inventory')).toBeInTheDocument();
  });

  it('guides the user to run analysis again instead of showing a generic error when no sealed snapshot exists (#178)', () => {
    mockInsights({ data: null, status: 'error', success: false, noSnapshot: true });

    renderPage();

    expect(screen.getByText('No sealed snapshot yet')).toBeInTheDocument();
    expect(
      screen.getByText(
        'This repository has no sealed Repository Intelligence snapshot for its current revision. Analyse it again to generate one.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /run analysis/i })).toBeInTheDocument();
    expect(screen.queryByText('Extractor inventory')).not.toBeInTheDocument();
  });

  it('keeps a genuine error distinct from the no-snapshot state', () => {
    mockInsights({ data: null, status: 'error', success: false, error: 'Insights service is unavailable.' });

    renderPage();

    expect(screen.getByText('Insights service is unavailable.')).toBeInTheDocument();
    expect(screen.queryByText('No sealed snapshot yet')).not.toBeInTheDocument();
  });
});
