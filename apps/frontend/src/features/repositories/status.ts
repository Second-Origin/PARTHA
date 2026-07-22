import type { Repository } from '@/shared/types';

export const repositoryStatusVariant: Record<Repository['status'], 'info' | 'warning' | 'success' | 'error'> = {
  uploading: 'info',
  analysing: 'warning',
  completed: 'success',
  cancelled: 'warning',
  error: 'error',
};
