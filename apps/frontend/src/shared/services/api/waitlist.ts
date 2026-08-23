import { api } from './client';
import type { RequestConfig } from './client';
import type { WaitlistSignupRequest, WaitlistSignupResponse } from './types';

export const waitlistService = {
  join(request: WaitlistSignupRequest, config?: RequestConfig): Promise<WaitlistSignupResponse> {
    return api.post('/waitlist', request, config);
  },
};
