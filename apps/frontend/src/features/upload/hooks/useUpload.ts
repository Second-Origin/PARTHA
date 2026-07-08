import { useCallback, useMemo, useState } from 'react';
import type { DataSource, Repository, UploadFile } from '@/shared/types';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';
import { formatFileSize } from '@/shared/utils/cn';
import { useAppStore } from '@/app/store/useAppStore';
import { useRepository } from '@/features/repositories/hooks/useRepository';

export const MAX_FILE_SIZE = 100 * 1024 * 1024;

export const ACCEPTED_ARCHIVE_TYPES: Record<string, string[]> = {
  'application/zip': ['.zip'],
  'application/x-zip-compressed': ['.zip'],
  'application/x-tar': ['.tar'],
  'application/gzip': ['.gz', '.tar.gz'],
  'application/x-gzip': ['.gz', '.tar.gz'],
  'application/x-compressed-tar': ['.tar.gz'],
};

function getRepositoryNameFromArchive(fileName: string): string {
  return fileName.replace(/\.(zip|tar\.gz|tar|tgz|gz)$/i, '');
}

export function useUpload() {
  const { repositories, selectRepository } = useRepository();
  const addRepository = useAppStore((state) => state.addRepository);
  const startAnalysis = useAppStore((state) => state.startAnalysis);
  const [uploadFile, setUploadFile] = useState<UploadFile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dataSource: DataSource = 'real';

  const repositoryNames = useMemo(
    () => new Set(repositories.map((repo) => repo.name.toLowerCase())),
    [repositories],
  );

  const selectFile = useCallback(
    (acceptedFiles: File[]) => {
      setError(null);
      const file = acceptedFiles[0];
      if (!file) return;

      if (file.size > MAX_FILE_SIZE) {
        setError(`File too large. Maximum size is ${formatFileSize(MAX_FILE_SIZE)}.`);
        return;
      }

      const repoName = getRepositoryNameFromArchive(file.name);
      if (repositoryNames.has(repoName.toLowerCase())) {
        setError(`A repository named "${repoName}" already exists.`);
        return;
      }

      setUploadFile({
        file,
        name: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified,
      });
    },
    [repositoryNames],
  );

  const rejectFile = useCallback(() => {
    setError('Invalid file type. Please upload a ZIP or TAR.GZ file.');
  }, []);

  const removeFile = useCallback(() => {
    setUploadFile(null);
    setError(null);
  }, []);

  const analyseFile = useCallback(async (): Promise<Repository | null> => {
    if (!uploadFile) return null;
    setLoading(true);
    setError(null);

    try {
      const repoName = getRepositoryNameFromArchive(uploadFile.name);
      const uploadedRepository = await backendService.uploadRepository(uploadFile.file, { name: repoName });

      if (!uploadedRepository) {
        throw new Error('Upload did not return a repository.');
      }

      if (uploadedRepository) {
        await backendService.startAnalysis(uploadedRepository.id);
      }

      const repository: Repository = {
        ...uploadedRepository,
        status: 'analysing',
        analysisStage: uploadedRepository.analysisStage || 'uploading',
      };

      addRepository(repository);
      selectRepository(repository);
      startAnalysis(repository.id);
      setUploadFile(null);
      return repository;
    } catch (caught) {
      setError(getErrorMessage(caught));
      return null;
    } finally {
      setLoading(false);
    }
  }, [addRepository, selectRepository, startAnalysis, uploadFile]);

  const clearError = useCallback(() => setError(null), []);

  return {
    uploadFile,
    loading,
    error,
    empty: !uploadFile,
    success: Boolean(uploadFile),
    source: dataSource,
    selectFile,
    rejectFile,
    removeFile,
    analyseFile,
    retry: clearError,
    refresh: clearError,
  };
}
