import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { documentationService, exportService } from './documentation';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('documentationService', () => {
  it('generate posts the request body to /documentation/generate', async () => {
    const request = { repositoryId: 'repo-1', sections: ['overview'] };
    const response = { content: '# Docs' };
    vi.mocked(api.post).mockResolvedValue(response);

    const result = await documentationService.generate(request as never);

    expect(api.post).toHaveBeenCalledWith('/documentation/generate', request, undefined);
    expect(result).toBe(response);
  });

  it('propagates a rejected generate request', async () => {
    const error = new Error('generation failed');
    vi.mocked(api.post).mockRejectedValue(error);

    await expect(documentationService.generate({} as never)).rejects.toBe(error);
  });
});

describe('exportService', () => {
  it('export posts the request body to /export', async () => {
    const request = { repositoryId: 'repo-1', target: 'review', format: 'json' };
    const response = { filename: 'review.json', mediaType: 'application/json', encoding: 'utf-8', content: '{}' };
    vi.mocked(api.post).mockResolvedValue(response);

    const result = await exportService.export(request as never);

    expect(api.post).toHaveBeenCalledWith('/export', request, undefined);
    expect(result).toBe(response);
  });

  it('propagates a rejected export request', async () => {
    const error = new Error('export failed');
    vi.mocked(api.post).mockRejectedValue(error);

    await expect(exportService.export({} as never)).rejects.toBe(error);
  });
});
