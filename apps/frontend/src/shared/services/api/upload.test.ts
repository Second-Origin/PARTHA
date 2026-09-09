import { describe, expect, it, vi } from 'vitest';
import { uploadFile } from './client';
import { uploadService } from './upload';

vi.mock('./client', () => ({
  uploadFile: vi.fn(),
}));

describe('uploadService', () => {
  it('uploadRepository sends the file to /repositories/upload with its fields', async () => {
    const response = { id: 'repo-1' };
    vi.mocked(uploadFile).mockResolvedValue(response);
    const file = new File(['content'], 'repo.zip', { type: 'application/zip' });

    const result = await uploadService.uploadRepository(file, { name: 'repo', description: 'desc' });

    expect(uploadFile).toHaveBeenCalledWith(
      '/repositories/upload',
      file,
      { name: 'repo', description: 'desc' },
      undefined,
    );
    expect(result).toBe(response);
  });

  it('uploadRepository works with no optional fields', async () => {
    vi.mocked(uploadFile).mockResolvedValue({ id: 'repo-1' });
    const file = new File(['content'], 'repo.zip', { type: 'application/zip' });

    await uploadService.uploadRepository(file);

    expect(uploadFile).toHaveBeenCalledWith('/repositories/upload', file, undefined, undefined);
  });

  it('propagates a rejected upload (e.g. a size-cap violation) rather than swallowing it', async () => {
    const error = new Error('archive exceeds the size cap');
    vi.mocked(uploadFile).mockRejectedValue(error);
    const file = new File(['content'], 'repo.zip', { type: 'application/zip' });

    await expect(uploadService.uploadRepository(file)).rejects.toBe(error);
  });
});
