import { api, streamRequest } from './client';
import type { RequestConfig } from './client';
import type {
  AiQueryRequest,
  AiQueryResponse,
  AiStreamChunk,
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

  streamQuery(
    request: AiQueryRequest,
    onChunk: (chunk: AiStreamChunk) => void,
    config?: RequestConfig,
  ): Promise<void> {
    return streamRequest(
      '/ai/stream',
      request,
      (rawChunk) => {
        const lines = rawChunk.split('\n').filter((l) => l.startsWith('data: '));
        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6)) as AiStreamChunk;
            onChunk(data);
          } catch {
            onChunk({ type: 'content', content: line.slice(6) });
          }
        }
      },
      config,
    );
  },
};
