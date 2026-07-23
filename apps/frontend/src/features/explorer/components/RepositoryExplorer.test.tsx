import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { FileTreeNode } from '@/shared/types';
import { repositoryService } from '@/shared/services/api/repositories';
import { useExplorerStore } from '../store';
import { RepositoryExplorer } from './RepositoryExplorer';

vi.mock('@/shared/services/api/repositories', () => ({
  repositoryService: {
    getFile: vi.fn(),
  },
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({ value }: { value: string }) => <pre data-testid="editor-stub">{value}</pre>,
}));

const mockedGetFile = vi.mocked(repositoryService.getFile);

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
  });

  it('opens and highlights the exact cited file and line span', async () => {
    render(
      <RepositoryExplorer
        fileTree={FILE_TREE}
        repositoryId="repo-1"
        citation={{ path: 'src/dependencies.py', startLine: 6, endLine: 7, snapshotId: 'snap_1' }}
      />,
    );

    expect(await screen.findByTestId('editor-stub')).toBeInTheDocument();
    expect(screen.getByText(/Cited lines 6-7/)).toBeInTheDocument();
    expect(screen.getByText(/snapshot snap_1/)).toBeInTheDocument();
    expect(mockedGetFile).toHaveBeenCalledWith('repo-1', 'src/dependencies.py');
  });

  it('shows no citation banner when there is no deep-link', async () => {
    render(<RepositoryExplorer fileTree={FILE_TREE} repositoryId="repo-1" citation={null} />);

    expect(screen.getByText('Select a file from the explorer')).toBeInTheDocument();
    expect(screen.queryByText(/Cited lines/)).not.toBeInTheDocument();
  });
});
