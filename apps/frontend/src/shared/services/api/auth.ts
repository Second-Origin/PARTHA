import { api } from './client';
import type { RequestConfig } from './client';
import type {
  AccountDeletionRequest,
  AuthResponse,
  LoginRequest,
  OAuthLinkConfirmRequest,
  OAuthLinkedIdentitiesResponse,
  OAuthProvider,
  OAuthProvidersResponse,
  OAuthStartResponse,
  RegisterRequest,
  UserResponse,
} from './types';

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

  deleteAccount(request: AccountDeletionRequest, config?: RequestConfig): Promise<void> {
    return api.delete('/auth/me', request, config);
  },

  // #288: Google/GitHub sign-in, credentials deferred. getOAuthProviders()
  // is the capability gate -- the frontend only ever renders a "Continue
  // with ..." button, or a linked-account row, for a provider this reports.
  getOAuthProviders(config?: RequestConfig): Promise<OAuthProvidersResponse> {
    return api.get('/auth/oauth/providers', config);
  },

  startOAuthLogin(provider: OAuthProvider, config?: RequestConfig): Promise<OAuthStartResponse> {
    return api.get(`/auth/oauth/${provider}/start`, config);
  },

  startOAuthLink(provider: OAuthProvider, config?: RequestConfig): Promise<OAuthStartResponse> {
    return api.post(`/auth/oauth/${provider}/link`, undefined, config);
  },

  confirmOAuthLink(request: OAuthLinkConfirmRequest, config?: RequestConfig): Promise<AuthResponse> {
    return api.post('/auth/oauth/link/confirm', request, config);
  },

  listLinkedOAuthIdentities(config?: RequestConfig): Promise<OAuthLinkedIdentitiesResponse> {
    return api.get('/auth/oauth/linked', config);
  },

  unlinkOAuthProvider(provider: OAuthProvider, config?: RequestConfig): Promise<void> {
    return api.delete(`/auth/oauth/${provider}`, undefined, config);
  },
};
