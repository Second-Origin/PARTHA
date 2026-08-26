import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Repository } from '@/shared/types';
import { useUpload } from '@/features/upload/hooks/useUpload';
import { useGitHubImport } from '@/features/upload/hooks/useGitHubImport';
import { UploadPage } from './UploadPage';

const navigateMock = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigateMock };
});

vi.mock('@/features/upload/hooks/useUpload', async () => {
  const actual = await vi.importActual<typeof import('@/features/upload/hooks/useUpload')>(
    '@/features/upload/hooks/useUpload',
  );
  return { ...actual, useUpload: vi.fn() };
});

vi.mock('@/features/upload/hooks/useGitHubImport', () => ({
  useGitHubImport: vi.fn(),
}));

// react-dropzone reads File.prototype internals jsdom doesn't fully implement;
// the file-selection/drag-drop path itself is already covered by useUpload's
// own hook tests (selectFile/rejectFile), so UploadPage's tests exercise the
// page's own wiring (button gating, error/preview rendering, post-analysis
// navigation) against whatever state the hook reports, not react-dropzone
// internals.

function baseUpload(overrides: Partial<ReturnType<typeof useUpload>> = {}): ReturnType<typeof useUpload> {
  return {
    uploadFile: null,
    loading: false,
    error: null,
    empty: true,
    success: false,
    source: 'upload',
    selectFile: vi.fn(),
    rejectFile: vi.fn(),
    removeFile: vi.fn(),
    analyseFile: vi.fn(),
    retry: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  };
}

function baseGithubImport(
  overrides: Partial<ReturnType<typeof useGitHubImport>> = {},
): ReturnType<typeof useGitHubImport> {
  return {
    githubUrl: '',
    setGithubUrl: vi.fn(),
    loading: false,
    error: null,
    empty: true,
    success: false,
    source: 'github',
    previewName: null,
    analyseGithub: vi.fn(),
    retry: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <UploadPage />
    </MemoryRouter>,
  );
}

const repository: Repository = {
  id: 'repo-1',
  name: 'sample',
  source: 'upload',
  size: 10,
  fileCount: 5,
  status: 'completed',
  analysisStage: 'completed',
  analysisProgress: 100,
  uploadedAt: '2026-08-02T08:00:00Z',
  meta: null,
  fileTree: [],
};

describe('UploadPage', () => {
  beforeEach(() => {
    navigateMock.mockClear();
    vi.mocked(useUpload).mockReturnValue(baseUpload());
    vi.mocked(useGitHubImport).mockReturnValue(baseGithubImport());
  });

  describe('source tabs', () => {
    it('keeps the selected tab and visible panel in sync', async () => {
      renderPage();

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

  describe('archive upload', () => {
    it('has no submit button until a file is selected', () => {
      renderPage();

      expect(screen.queryByRole('button', { name: /Analyse Repository/i })).not.toBeInTheDocument();
    });

    it('shows the selected file with its real name and size, and a working remove control', () => {
      const removeFile = vi.fn();
      vi.mocked(useUpload).mockReturnValue(
        baseUpload({
          uploadFile: { file: new File(['x'], 'my-repo.zip'), name: 'my-repo.zip', size: 2048, type: 'application/zip', lastModified: 0 },
          empty: false,
          success: true,
          removeFile,
        }),
      );

      renderPage();

      expect(screen.getByText('my-repo.zip')).toBeInTheDocument();
      expect(screen.getByText('2 KB')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Analyse Repository/i })).toBeInTheDocument();

      const removeButton = screen.getByText('my-repo.zip').closest('div.rounded-2xl')?.querySelector('button');
      expect(removeButton).not.toBeNull();
      fireEvent.click(removeButton!);
      expect(removeFile).toHaveBeenCalled();
    });

    it('surfaces a rejected-file error honestly, not a fabricated success state', () => {
      vi.mocked(useUpload).mockReturnValue(
        baseUpload({ error: 'Invalid file type. Please upload a ZIP, TAR, TAR.GZ, or TGZ file.' }),
      );

      renderPage();

      expect(
        screen.getByText('Invalid file type. Please upload a ZIP, TAR, TAR.GZ, or TGZ file.'),
      ).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Analyse Repository/i })).not.toBeInTheDocument();
    });

    it('navigates to the repository detail page once analysis completes synchronously', async () => {
      const analyseFile = vi.fn().mockResolvedValue(repository);
      vi.mocked(useUpload).mockReturnValue(
        baseUpload({
          uploadFile: { file: new File(['x'], 'a.zip'), name: 'a.zip', size: 10, type: 'application/zip', lastModified: 0 },
          empty: false,
          success: true,
          analyseFile,
        }),
      );

      renderPage();
      fireEvent.click(screen.getByRole('button', { name: /Analyse Repository/i }));

      await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/repositories/repo-1'));
    });

    it('navigates to the analysis progress page when the repository is still analysing', async () => {
      const analysing: Repository = { ...repository, status: 'analysing' };
      const analyseFile = vi.fn().mockResolvedValue(analysing);
      vi.mocked(useUpload).mockReturnValue(
        baseUpload({
          uploadFile: { file: new File(['x'], 'a.zip'), name: 'a.zip', size: 10, type: 'application/zip', lastModified: 0 },
          empty: false,
          success: true,
          analyseFile,
        }),
      );

      renderPage();
      fireEvent.click(screen.getByRole('button', { name: /Analyse Repository/i }));

      await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/analysis/repo-1'));
    });

    it('does not navigate when analysis fails to return a repository', async () => {
      const analyseFile = vi.fn().mockResolvedValue(null);
      vi.mocked(useUpload).mockReturnValue(
        baseUpload({
          uploadFile: { file: new File(['x'], 'a.zip'), name: 'a.zip', size: 10, type: 'application/zip', lastModified: 0 },
          empty: false,
          success: true,
          analyseFile,
        }),
      );

      renderPage();
      fireEvent.click(screen.getByRole('button', { name: /Analyse Repository/i }));

      await waitFor(() => expect(analyseFile).toHaveBeenCalled());
      expect(navigateMock).not.toHaveBeenCalled();
    });
  });

  describe('GitHub import', () => {
    async function githubPanel() {
      fireEvent.click(screen.getByRole('tab', { name: 'GitHub URL' }));
      // AnimatePresence swaps the panel asynchronously (exit animation before
      // the new panel mounts); the tab's aria-selected flips immediately, but
      // the panel content does not.
      await waitFor(() => expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'upload-github-panel'));
    }

    it('disables submit until a URL is entered', async () => {
      renderPage();
      await githubPanel();

      expect(screen.getByRole('button', { name: /Analyse Repository/i })).toBeDisabled();
    });

    it('enables submit once a URL is entered', async () => {
      vi.mocked(useGitHubImport).mockReturnValue(
        baseGithubImport({ githubUrl: 'https://github.com/example/repo', empty: false, success: true }),
      );

      renderPage();
      await githubPanel();

      expect(screen.getByRole('button', { name: /Analyse Repository/i })).toBeEnabled();
    });

    it('renders a live preview of the resolved repository name for a valid URL', async () => {
      vi.mocked(useGitHubImport).mockReturnValue(
        baseGithubImport({ githubUrl: 'https://github.com/example/repo', success: true, previewName: 'repo' }),
      );

      renderPage();
      await githubPanel();

      expect(screen.getByText('repo', { selector: 'span' })).toBeInTheDocument();
    });

    it('surfaces an invalid-URL error honestly rather than a fabricated preview', async () => {
      vi.mocked(useGitHubImport).mockReturnValue(
        baseGithubImport({
          githubUrl: 'not-a-url',
          error: 'Invalid GitHub URL. Format: https://github.com/owner/repository',
        }),
      );

      renderPage();
      await githubPanel();

      expect(
        screen.getByText('Invalid GitHub URL. Format: https://github.com/owner/repository'),
      ).toBeInTheDocument();
    });

    it('typing into the URL field calls setGithubUrl with the raw input', async () => {
      const setGithubUrl = vi.fn();
      vi.mocked(useGitHubImport).mockReturnValue(baseGithubImport({ setGithubUrl }));

      renderPage();
      await githubPanel();
      fireEvent.change(screen.getByTestId('github-import-url'), {
        target: { value: 'https://github.com/example/repo' },
      });

      expect(setGithubUrl).toHaveBeenCalledWith('https://github.com/example/repo');
    });

    it('navigates to the repository detail page once a completed import resolves', async () => {
      const analyseGithub = vi.fn().mockResolvedValue(repository);
      vi.mocked(useGitHubImport).mockReturnValue(
        baseGithubImport({ githubUrl: 'https://github.com/example/repo', success: true, analyseGithub }),
      );

      renderPage();
      await githubPanel();
      fireEvent.click(screen.getByRole('button', { name: /Analyse Repository/i }));

      await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/repositories/repo-1'));
    });
  });
});
