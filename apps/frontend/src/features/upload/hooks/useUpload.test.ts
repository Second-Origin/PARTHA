import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '@/app/store/useAppStore';
import { backendService } from '@/shared/services/backend';
import type { Repository } from '@/shared/types';
import { ACCEPTED_ARCHIVE_TYPES, MAX_FILE_SIZE, useUpload } from './useUpload';

const repositoryState = vi.hoisted(() => ({
  repositories: [] as Repository[],
  selectRepository: vi.fn(),
}));

vi.mock('@/features/repositories/hooks/useRepository', () => ({
  useRepository: () => ({
    repositories: repositoryState.repositories,
    selectRepository: repositoryState.selectRepository,
  }),
}));

const LAST_MODIFIED = 1_700_000_000_000;

function repository(id: string, name: string): Repository {
  return {
    id,
    name,
    source: 'upload',
    size: 0,
    fileCount: 0,
    status: 'uploading',
    dataSource: 'real',
    analysisStage: 'uploading',
    analysisProgress: 0,
    uploadedAt: '2026-01-01T00:00:00Z',
    meta: null,
    fileTree: [],
  };
}

function archiveFile(name: string, type = 'application/zip'): File {
  return new File(['archive'], name, { type, lastModified: LAST_MODIFIED });
}

function oversizedArchiveFile(): File {
  const file = archiveFile('too-large.zip');
  Object.defineProperty(file, 'size', { value: MAX_FILE_SIZE + 1 });
  return file;
}

function mockUpload() {
  return vi.spyOn(backendService, 'uploadRepository').mockResolvedValue(null);
}

describe('useUpload', () => {
  beforeEach(() => {
    repositoryState.repositories = [];
    repositoryState.selectRepository.mockReset();
    useAppStore.setState({ repositories: [], activeRepositoryId: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('handles an empty file selection without starting an upload', () => {
    const uploadRepository = mockUpload();
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.rejectFile();
    });

    act(() => {
      hook.result.current.selectFile([]);
    });

    expect(hook.result.current.uploadFile).toBeNull();
    expect(hook.result.current.loading).toBe(false);
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.empty).toBe(true);
    expect(hook.result.current.success).toBe(false);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it('rejects an archive larger than 100 MiB with the exact user-facing error', () => {
    const uploadRepository = mockUpload();
    const file = oversizedArchiveFile();
    const hook = renderHook(() => useUpload());

    expect(file.size).toBe(MAX_FILE_SIZE + 1);

    act(() => {
      hook.result.current.selectFile([archiveFile('accepted.zip')]);
    });

    act(() => {
      hook.result.current.selectFile([file]);
    });

    expect(hook.result.current.uploadFile).toBeNull();
    expect(hook.result.current.error).toBe('File too large. Maximum size is 100 MB.');
    expect(hook.result.current.empty).toBe(true);
    expect(hook.result.current.success).toBe(false);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it('accepts an archive of exactly the maximum size', () => {
    const uploadRepository = mockUpload();
    const file = archiveFile('at-limit.zip');
    Object.defineProperty(file, 'size', { value: MAX_FILE_SIZE });
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.selectFile([file]);
    });

    expect(hook.result.current.uploadFile?.size).toBe(MAX_FILE_SIZE);
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.empty).toBe(false);
    expect(hook.result.current.success).toBe(true);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it('rejects duplicate archive repository names case-insensitively', () => {
    repositoryState.repositories = [repository('existing-id', 'Existing-Project')];
    const uploadRepository = mockUpload();
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.selectFile([archiveFile('new-project.zip')]);
    });

    act(() => {
      hook.result.current.selectFile([archiveFile('existing-project.TAR.GZ', 'application/gzip')]);
    });

    expect(hook.result.current.uploadFile).toBeNull();
    expect(hook.result.current.error).toBe('A repository named "existing-project" already exists.');
    expect(hook.result.current.empty).toBe(true);
    expect(hook.result.current.success).toBe(false);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it.each([
    ['repository.zip', 'application/zip'],
    ['repository.tar', 'application/x-tar'],
    ['repository.tar.gz', 'application/gzip'],
    ['repository.tgz', 'application/gzip'],
  ])('selects an accepted archive and exposes its upload state: %s', (name, type) => {
    const uploadRepository = mockUpload();
    const file = archiveFile(name, type);
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.selectFile([file]);
    });

    expect(hook.result.current.uploadFile).toEqual({
      file,
      name,
      size: file.size,
      type,
      lastModified: LAST_MODIFIED,
    });
    expect(hook.result.current.loading).toBe(false);
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.empty).toBe(false);
    expect(hook.result.current.success).toBe(true);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it('accepts TAR-based gzip archives but not standalone gzip files', () => {
    expect(ACCEPTED_ARCHIVE_TYPES['application/gzip']).toContain('.tgz');
    expect(ACCEPTED_ARCHIVE_TYPES['application/x-gzip']).toContain('.tgz');
    expect(ACCEPTED_ARCHIVE_TYPES['application/x-compressed-tar']).toContain('.tgz');
    expect(ACCEPTED_ARCHIVE_TYPES['application/gzip']).toContain('.tar.gz');
    expect(ACCEPTED_ARCHIVE_TYPES['application/x-gzip']).toContain('.tar.gz');
    expect(ACCEPTED_ARCHIVE_TYPES['application/x-compressed-tar']).toContain('.tar.gz');
    expect(Object.values(ACCEPTED_ARCHIVE_TYPES).flat()).not.toContain('.gz');
  });

  it('reports a rejected archive type without retaining a previous selection', () => {
    const uploadRepository = mockUpload();
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.selectFile([archiveFile('accepted.zip')]);
    });

    act(() => {
      hook.result.current.rejectFile();
    });

    expect(hook.result.current.uploadFile).toBeNull();
    expect(hook.result.current.error).toBe('Invalid file type. Please upload a ZIP, TAR, TAR.GZ, or TGZ file.');
    expect(hook.result.current.empty).toBe(true);
    expect(hook.result.current.success).toBe(false);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it('selects only the first file from a multi-file selection', () => {
    const uploadRepository = mockUpload();
    const firstFile = archiveFile('first.zip');
    const secondFile = archiveFile('second.zip');
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.selectFile([firstFile, secondFile]);
    });

    expect(hook.result.current.uploadFile?.file).toBe(firstFile);
    expect(hook.result.current.uploadFile?.name).toBe('first.zip');
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.success).toBe(true);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it.each(['retry', 'refresh'] as const)('%s clears a validation error without restoring a selection', (action) => {
    const uploadRepository = mockUpload();
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.selectFile([archiveFile('accepted.zip')]);
    });

    act(() => {
      hook.result.current.rejectFile();
    });

    act(() => {
      hook.result.current[action]();
    });

    expect(hook.result.current.uploadFile).toBeNull();
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.empty).toBe(true);
    expect(hook.result.current.success).toBe(false);
    expect(uploadRepository).not.toHaveBeenCalled();
  });

  it('removes a selected archive and returns to the empty state', () => {
    const uploadRepository = mockUpload();
    const file = archiveFile('repository.zip');
    const hook = renderHook(() => useUpload());

    act(() => {
      hook.result.current.selectFile([file]);
    });

    act(() => {
      hook.result.current.removeFile();
    });

    expect(hook.result.current.uploadFile).toBeNull();
    expect(hook.result.current.error).toBeNull();
    expect(hook.result.current.empty).toBe(true);
    expect(hook.result.current.success).toBe(false);
    expect(uploadRepository).not.toHaveBeenCalled();
  });
});
