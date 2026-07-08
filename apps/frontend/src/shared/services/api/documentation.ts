import { api } from './client';
import type { RequestConfig } from './client';
import type { GenerateDocRequest, GenerateDocResponse, ExportRequest, ExportResponse } from './types';

export const documentationService = {
  generate(request: GenerateDocRequest, config?: RequestConfig): Promise<GenerateDocResponse> {
    return api.post('/documentation/generate', request, config);
  },
};

export const exportService = {
  export(request: ExportRequest, config?: RequestConfig): Promise<ExportResponse> {
    return api.post('/export', request, config);
  },
};
