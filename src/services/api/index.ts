export { api, configureApiClient, getApiConfig, uploadFile, streamRequest } from './client';
export type { RequestConfig, ApiClientConfig, HttpMethod } from './client';

export { ApiError, NetworkError, TimeoutError, CancelledError, isApiError, isNetworkError, isTimeoutError, isCancelledError, getErrorMessage } from './errors';

export { repositoryService } from './repositories';
export { uploadService } from './upload';
export { analysisService } from './analysis';
export { architectureService } from './architecture';
export { reviewService } from './review';
export { dependencyService } from './dependencies';
export { aiService } from './ai';
export { documentationService, exportService } from './documentation';

export type * from './types';
