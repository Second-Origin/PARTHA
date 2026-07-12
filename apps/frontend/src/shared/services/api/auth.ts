import { api } from './client';
import type { RequestConfig } from './client';
import type { AuthResponse, LoginRequest, RegisterRequest, UserResponse } from './types';

export const authService = {
  register(request: RegisterRequest, config?: RequestConfig): Promise<AuthResponse> {
    return api.post('/auth/register', request, config);
  },

  login(request: LoginRequest, config?: RequestConfig): Promise<AuthResponse> {
    return api.post('/auth/login', request, config);
  },

  refresh(config?: RequestConfig): Promise<AuthResponse> {
    return api.post('/auth/refresh', undefined, config);
  },

  logout(config?: RequestConfig): Promise<void> {
    return api.post('/auth/logout', undefined, config);
  },

  me(config?: RequestConfig): Promise<UserResponse> {
    return api.get('/auth/me', config);
  },
};
