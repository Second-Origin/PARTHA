export type AppStatus = 'empty' | 'repository-selected' | 'uploading' | 'analysing' | 'completed' | 'cancelled' | 'error';

export type RepositorySource = 'upload' | 'github';
export type FeatureStatus = 'idle' | 'loading' | 'success' | 'error' | 'empty';

export type AnalysisStage =
  | 'uploading'
  | 'extracting'
  | 'reading-structure'
  | 'detecting-languages'
  | 'detecting-framework'
  | 'building-file-tree'
  | 'extracting-modules'
  | 'building-dependency-graph'
  | 'preparing-architecture'
  | 'completed';

export const ANALYSIS_STAGES: { key: AnalysisStage; label: string }[] = [
  { key: 'uploading', label: 'Uploading Repository' },
  { key: 'extracting', label: 'Extracting Files' },
  { key: 'reading-structure', label: 'Reading Repository Structure' },
  { key: 'detecting-languages', label: 'Detecting Languages' },
  { key: 'detecting-framework', label: 'Detecting Framework' },
  { key: 'building-file-tree', label: 'Building File Tree' },
  { key: 'extracting-modules', label: 'Extracting Modules' },
  { key: 'building-dependency-graph', label: 'Building Dependency Graph' },
  { key: 'preparing-architecture', label: 'Preparing Architecture Model' },
  { key: 'completed', label: 'Analysis Complete' },
];

export interface FileTreeNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  path: string;
  children?: FileTreeNode[];
  size?: number;
  extension?: string;
  language?: string;
}

export interface RepositoryMeta {
  language: string;
  framework: string;
  totalFiles: number;
  totalFolders: number;
  entryPoint: string | null;
  configFiles: string[];
  packageManager: string | null;
  hasReadme: boolean;
  hasLicense: boolean;
  licenseName: string | null;
}

export interface RepositoryRevision {
  kind: 'git' | 'upload';
  value: string;
  ref: string | null;
}

export interface Repository {
  id: string;
  name: string;
  description?: string;
  source: RepositorySource;
  sourceUrl?: string;
  size: number;
  fileCount: number;
  status: 'uploading' | 'analysing' | 'completed' | 'cancelled' | 'error';
  analysisStage: AnalysisStage | null;
  analysisProgress: number;
  uploadedAt: string;
  analysedAt?: string;
  errorMessage?: string;
  revision?: RepositoryRevision | null;
  commitSha?: string | null;
  meta: RepositoryMeta | null;
  fileTree: FileTreeNode[];
}

export interface UploadFile {
  file: File;
  name: string;
  size: number;
  type: string;
  lastModified: number;
}

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  read: boolean;
  createdAt: string;
}
