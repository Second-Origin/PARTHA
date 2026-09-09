import { describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { waitlistService } from './waitlist';

vi.mock('./client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

describe('waitlistService', () => {
  it('join posts the request body to /waitlist', async () => {
    const request = { email: 'a@b.com', name: 'A' };
    const response = { status: 'confirmed' };
    vi.mocked(api.post).mockResolvedValue(response);

    const result = await waitlistService.join(request as never);

    expect(api.post).toHaveBeenCalledWith('/waitlist', request, undefined);
    expect(result).toBe(response);
  });

  it('propagates a rejected request (e.g. a duplicate signup) rather than swallowing it', async () => {
    const error = new Error('already on the waitlist');
    vi.mocked(api.post).mockRejectedValue(error);

    await expect(waitlistService.join({} as never)).rejects.toBe(error);
  });
});
