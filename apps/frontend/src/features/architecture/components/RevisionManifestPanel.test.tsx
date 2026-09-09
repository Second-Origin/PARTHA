import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { architectureService } from '@/shared/services/api/architecture';
import type { RevisionManifestResponse } from '@/shared/services/api/types';
import { RevisionManifestPanel } from './RevisionManifestPanel';

vi.mock('@/shared/services/api/architecture', () => ({
  architectureService: { getRevisionManifest: vi.fn() },
}));

const mockedGetManifest = vi.mocked(architectureService.getRevisionManifest);

const response: RevisionManifestResponse = {
  manifest: {
    schemaVersion: 'revision-manifest.v1',
    repositoryId: 'repo-1',
    revisionKind: 'upload',
    revisionValue: `sha256:${'0'.repeat(64)}`,
    revisionRef: null,
    snapshotId: 'snap_example',
    snapshotSchemaVersion: 'ri.v1',
    extractors: [
      { name: 'typescript-extractor', version: '1.0.0' },
      { name: 'relationship-resolver', version: '1.0.0' },
    ],
    producerSetHash: `sha256:${'1'.repeat(64)}`,
    configHash: `sha256:${'2'.repeat(64)}`,
    canonicalGraphHash: `sha256:${'3'.repeat(64)}`,
    createdAt: '2026-07-25T00:00:00Z',
    sealedAt: '2026-07-25T00:00:05Z',
  },
  manifestDigest: `sha256:${'4'.repeat(64)}`,
  verificationMethod: 'sha256-canonical-json',
  verificationState: 'verified',
  verificationNote:
    'This digest is a SHA-256 over the canonical JSON encoding of the manifest fields above. It is a content hash, not a digital signature.',
};

describe('RevisionManifestPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('stays collapsed by default so it cannot crowd out the graph', async () => {
    // Browser review of #112 found the expanded panel squeezing the
    // architecture graph into a thin strip. The graph is the primary content
    // on this page, so detail is opt-in.
    mockedGetManifest.mockResolvedValue(response);

    render(<RevisionManifestPanel repositoryId="repo-1" />);

    await waitFor(() => expect(screen.getByTestId('revision-manifest')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /details/i })).toHaveAttribute('aria-expanded', 'false');
    // The identity that binds citations to a revision stays visible collapsed.
    expect(screen.getByText('snap_example')).toBeInTheDocument();
    expect(screen.getByTestId('verification-state')).toHaveTextContent('verified');
    // Detail is not rendered until asked for.
    expect(screen.queryByText('ri.v1')).not.toBeInTheDocument();
    expect(screen.queryByText(/not a digital signature/)).not.toBeInTheDocument();
  });

  it('shows the revision identity, extractor versions and digest', async () => {
    mockedGetManifest.mockResolvedValue(response);

    render(<RevisionManifestPanel repositoryId="repo-1" />);

    await waitFor(() => expect(screen.getByTestId('revision-manifest')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /details/i }));
    expect(screen.getByText('snap_example')).toBeInTheDocument();
    expect(screen.getByText('ri.v1')).toBeInTheDocument();
    expect(screen.getByText(`sha256:${'4'.repeat(64)}`)).toBeInTheDocument();
    expect(screen.getByText('typescript-extractor@1.0.0')).toBeInTheDocument();
    expect(screen.getByTestId('verification-state')).toHaveTextContent('verified');
  });

  it('states that the digest is a content hash rather than a signature', async () => {
    mockedGetManifest.mockResolvedValue(response);

    render(<RevisionManifestPanel repositoryId="repo-1" />);

    await waitFor(() => expect(screen.getByTestId('revision-manifest')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /details/i }));
    expect(screen.getByText(/not a digital signature/)).toBeInTheDocument();
  });

  it('copies the exact response body so it can be re-verified later', async () => {
    mockedGetManifest.mockResolvedValue(response);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<RevisionManifestPanel repositoryId="repo-1" />);
    await waitFor(() => expect(screen.getByTestId('revision-manifest')).toBeInTheDocument());

    screen.getByRole('button', { name: /copy/i }).click();

    await waitFor(() => expect(writeText).toHaveBeenCalledOnce());
    expect(JSON.parse(writeText.mock.calls[0][0])).toEqual(response);
  });

  it('reports an honest unavailable state instead of inventing a revision', async () => {
    mockedGetManifest.mockRejectedValue(new Error('No sealed snapshot is available.'));

    render(<RevisionManifestPanel repositoryId="repo-1" />);

    await waitFor(() =>
      expect(screen.getByText(/No revision manifest is available/)).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('revision-manifest')).not.toBeInTheDocument();
  });
});
