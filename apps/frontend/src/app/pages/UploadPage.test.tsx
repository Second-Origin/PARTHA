import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { UploadPage } from './UploadPage';

vi.mock('@/features/upload/hooks/useUpload', () => ({
  ACCEPTED_ARCHIVE_TYPES: { 'application/zip': ['.zip'] },
  MAX_FILE_SIZE: 1024,
  useUpload: () => ({
    selectFile: vi.fn(), rejectFile: vi.fn(), retry: vi.fn(), source: 'upload',
    uploadFile: null, error: null, loading: false, analyseFile: vi.fn(),
    removeFile: vi.fn(),
  }),
}));

vi.mock('@/features/upload/hooks/useGitHubImport', () => ({
  useGitHubImport: () => ({
    retry: vi.fn(), source: 'github', githubUrl: '', setGithubUrl: vi.fn(),
    previewName: null, error: null, loading: false, analyseGithub: vi.fn(),
  }),
}));

describe('UploadPage source tabs', () => {
  it('keeps the selected tab and visible panel in sync', async () => {
    render(<MemoryRouter><UploadPage /></MemoryRouter>);

    const fileTab = screen.getByRole('tab', { name: 'Upload File' });
    const githubTab = screen.getByRole('tab', { name: 'GitHub URL' });
    expect(fileTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'upload-file-panel');

    fireEvent.click(githubTab);

    expect(githubTab).toHaveAttribute('aria-selected', 'true');
    expect(fileTab).toHaveAttribute('aria-selected', 'false');
    await waitFor(() => {
      expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'upload-github-panel');
    });
    expect(screen.getByTestId('github-import-title')).toHaveTextContent('Import from GitHub');
  });
});
