import { api } from './client';
import type { RequestConfig } from './client';
import type {
  AiConversationResponse,
  AiQueryRequest,
  AiQueryResponse,
  AiProviderConfig,
  AiProviderPublicConfig,
  AiProviderTestRequest,
  AiProviderTestResponse,
} from './types';

export const aiService = {
  getConfig(config?: RequestConfig): Promise<AiProviderPublicConfig> {
    return api.get('/ai/config', config);
  },

  saveConfig(request: AiProviderConfig, config?: RequestConfig): Promise<AiProviderPublicConfig> {
    return api.put('/ai/config', request, config);
  },

  testConfig(request: AiProviderTestRequest, config?: RequestConfig): Promise<AiProviderTestResponse> {
    return api.post('/ai/test', request, config);
  },

  query(request: AiQueryRequest, config?: RequestConfig): Promise<AiQueryResponse> {
    return api.post('/ai/query', request, config);
  },

  listConversations(repositoryId: string, config?: RequestConfig): Promise<AiConversationResponse> {
    return api.get(`/ai/conversations?repositoryId=${encodeURIComponent(repositoryId)}`, config);
  },

};
