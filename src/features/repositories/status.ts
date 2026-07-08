import type { Repository } from '@/types';

export const repositoryStatusVariant: Record<Repository['status'], 'info' | 'warning' | 'success' | 'error'> = {
  uploading: 'info',
  analysing: 'warning',
  completed: 'success',
  error: 'error',
};
