import { uploadFile } from './client';
import type { RequestConfig } from './client';
import type { RepositoryResponse } from './types';

export const uploadService = {
  uploadRepository(
    file: File,
    fields?: { name?: string; description?: string },
    config?: RequestConfig,
  ): Promise<RepositoryResponse> {
    return uploadFile<RepositoryResponse>(
      '/repositories/upload',
      file,
      fields as Record<string, string>,
      config,
    );
  },
};
