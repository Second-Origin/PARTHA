import type { Repository } from '@/shared/types';
import type { ArchitectureModel } from '@/shared/types/architecture';
import type { EngineeringReview } from '@/shared/types/review';
import type { AnalysisStartResponse, AnalysisStatusResponse, DependencyGraphResponse, RepositoryResponse } from './api/types';
import { repositoryService } from './api/repositories';
import { uploadService } from './api/upload';
import { analysisService } from './api/analysis';
import { architectureService } from './api/architecture';
import { reviewService } from './api/review';
import { dependencyService } from './api/dependencies';

const USE_BACKEND = true;

export const hasBackend = USE_BACKEND;

export const backendService = {
  async fetchRepositories(): Promise<Repository[]> {
    if (!USE_BACKEND) return [];
    const response = await repositoryService.list();
    return response.data.map(mapRepositoryResponse);
  },

  async fetchRepository(id: string): Promise<Repository | null> {
    if (!USE_BACKEND) return null;
    const response = await repositoryService.getById(id);
    return mapRepositoryResponse(response);
  },

  async uploadRepository(
    file: File,
    fields?: { name?: string; description?: string },
    onProgress?: (progress: number) => void,
  ): Promise<Repository | null> {
    if (!USE_BACKEND) return null;
    const response = await uploadService.uploadRepository(file, fields, {
      onUploadProgress: onProgress,
    });
    return mapRepositoryResponse(response);
  },

  async importFromGithub(url: string, branch?: string): Promise<Repository | null> {
    if (!USE_BACKEND) return null;
    const response = await repositoryService.importFromGithub({ url, branch });
    return mapRepositoryResponse(response);
  },

  async startAnalysis(repositoryId: string): Promise<AnalysisStartResponse | null> {
    if (!USE_BACKEND) return null;
    return analysisService.start(repositoryId);
  },

  async fetchAnalysisStatus(repositoryId: string): Promise<AnalysisStatusResponse | null> {
    if (!USE_BACKEND) return null;
    return analysisService.getStatus(repositoryId);
  },

  async cancelAnalysis(repositoryId: string): Promise<AnalysisStatusResponse | null> {
    if (!USE_BACKEND) return null;
    return analysisService.cancel(repositoryId);
  },

  async fetchArchitecture(repository: Repository): Promise<ArchitectureModel> {
    if (!USE_BACKEND) {
      throw new Error('Backend API is not configured.');
    }
    return architectureService.getArchitecture(repository.id);
  },

  async fetchReview(repository: Repository): Promise<EngineeringReview> {
    if (!USE_BACKEND) {
      throw new Error('Backend API is not configured.');
    }
    return reviewService.getReview(repository.id);
  },

  async fetchDependencyGraph(repositoryId: string): Promise<DependencyGraphResponse | null> {
    if (!USE_BACKEND) return null;
    return dependencyService.getDependencyGraph(repositoryId);
  },

  async deleteRepository(id: string): Promise<boolean> {
    if (!USE_BACKEND) return true;
    await repositoryService.delete(id);
    return true;
  },
};

function mapRepositoryResponse(response: RepositoryResponse): Repository {
  return {
    id: response.id,
    name: response.name,
    description: response.description || undefined,
    source: response.source,
    sourceUrl: response.sourceUrl || undefined,
    size: response.size,
    fileCount: response.fileCount,
    status: response.status,
    analysisStage: response.analysisStage,
    analysisProgress: response.analysisProgress,
    uploadedAt: response.uploadedAt,
    analysedAt: response.analysedAt || undefined,
    errorMessage: response.errorMessage || undefined,
    revision: response.revision,
    commitSha: response.commitSha,
    meta: response.meta,
    fileTree: response.fileTree,
  };
}
