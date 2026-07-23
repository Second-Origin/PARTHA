import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { FileTreeNode } from '@/shared/types';
import { repositoryService } from '@/shared/services/api/repositories';
import { architectureService } from '@/shared/services/api/architecture';
import { useExplorerStore } from '../store';
import { RepositoryExplorer } from './RepositoryExplorer';

vi.mock('@/shared/services/api/repositories', () => ({
  repositoryService: {
    getFile: vi.fn(),
  },
}));

vi.mock('@/shared/services/api/architecture', () => ({
  architectureService: {
    getEvidenceSource: vi.fn(),
  },
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({ value }: { value: string }) => <pre data-testid="editor-stub">{value}</pre>,
}));

const mockedGetFile = vi.mocked(repositoryService.getFile);
const mockedGetEvidenceSource = vi.mocked(architectureService.getEvidenceSource);

const FILE_TREE: FileTreeNode[] = [
  {
    id: 'src',
    name: 'src',
    type: 'folder',
    path: 'src',
    children: [
      {
        id: 'src/dependencies.py',
        name: 'dependencies.py',
        type: 'file',
        path: 'src/dependencies.py',
        extension: 'py',
      },
    ],
  },
];

describe('RepositoryExplorer citation deep-link', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useExplorerStore.setState({
      expandedFolders: new Set(),
      selectedFileId: null,
      selectedNode: null,
      detailsTab: 'details',
    });
    mockedGetFile.mockResolvedValue({
      path: 'src/dependencies.py',
      content: 'def get_current_user(token):\n    return token\n',
      size: 47,
      isBinary: false,
      isImage: false,
      mediaType: null,
      truncated: false,
    });
    mockedGetEvidenceSource.mockResolvedValue({
      schemaVersion: 'evidence-source.v1',
      repositoryId: 'repo-1',
      snapshotId: 'snap_1',
      factId: 'fact_1',
      revisionKind: 'upload',
      revisionValue: 'sha256:' + '0'.repeat(64),
      path: 'src/dependencies.py',
      startLine: 6,
      endLine: 7,
      status: 'ready',
      reason: null,
      content: 'def get_current_user(token):\n    return token\n',
      truncated: false,
      size: 47,
    });
  });

  it('opens the exact cited file, verifies it, and highlights the line span', async () => {
    render(
      <RepositoryExplorer
        fileTree={FILE_TREE}
        repositoryId="repo-1"
        citation={{
          path: 'src/dependencies.py',
          startLine: 6,
          endLine: 7,
          snapshotId: 'snap_1',
          factId: 'fact_1',
        }}
      />,
    );

    expect(await screen.findByTestId('editor-stub')).toBeInTheDocument();
    expect(screen.getByText(/Cited lines 6-7/)).toBeInTheDocument();
    expect(screen.getByText(/snapshot snap_1/)).toBeInTheDocument();
    expect(screen.getByText(/revision upload:sha256:0{64}/)).toBeInTheDocument();
    expect(mockedGetEvidenceSource).toHaveBeenCalledWith(
      'repo-1',
      'snap_1',
      'fact_1',
      'src/dependencies.py',
      6,
      7,
    );
    // Never the unverified, unversioned file endpoint for a citation.
    expect(mockedGetFile).not.toHaveBeenCalled();
  });

  it('shows an honest unavailable state instead of falling back to unverified content', async () => {
    mockedGetEvidenceSource.mockResolvedValue({
      schemaVersion: 'evidence-source.v1',
      repositoryId: 'repo-1',
      snapshotId: 'snap_1',
      factId: 'fact_1',
      revisionKind: 'upload',
      revisionValue: 'sha256:' + '0'.repeat(64),
      path: 'src/dependencies.py',
      startLine: 6,
      endLine: 7,
      status: 'unavailable',
      reason: 'The cited line span is outside the available source content.',
      content: null,
      truncated: false,
      size: 0,
    });

    render(
      <RepositoryExplorer
        fileTree={FILE_TREE}
        repositoryId="repo-1"
        citation={{
          path: 'src/dependencies.py',
          startLine: 6,
          endLine: 7,
          snapshotId: 'snap_1',
          factId: 'fact_1',
        }}
      />,
    );

    expect(await screen.findByText('Evidence source unavailable for this snapshot revision.')).toBeInTheDocument();
    expect(screen.getByText('The cited line span is outside the available source content.')).toBeInTheDocument();
    expect(screen.queryByTestId('editor-stub')).not.toBeInTheDocument();
    expect(screen.queryByText(/Cited lines/)).not.toBeInTheDocument();
  });

  it('shows no citation banner when there is no deep-link and uses the plain file endpoint', async () => {
    render(<RepositoryExplorer fileTree={FILE_TREE} repositoryId="repo-1" citation={null} />);

    expect(screen.getByText('Select a file from the explorer')).toBeInTheDocument();
    expect(screen.queryByText(/Cited lines/)).not.toBeInTheDocument();
    expect(mockedGetEvidenceSource).not.toHaveBeenCalled();
  });
});
