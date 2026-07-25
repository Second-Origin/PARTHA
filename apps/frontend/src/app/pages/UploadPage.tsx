import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  File,
  X,
  ArrowRight,
  AlertCircle,
  Github,
  Calendar,
  HardDrive,
  FileArchive,
} from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { ACCEPTED_ARCHIVE_TYPES, MAX_FILE_SIZE, useUpload } from '@/features/upload/hooks/useUpload';
import { useGitHubImport } from '@/features/upload/hooks/useGitHubImport';
import { formatFileSize } from '@/shared/utils/cn';
import { cn } from '@/shared/utils/cn';

type UploadMode = 'file' | 'github';

export function UploadPage() {
  const navigate = useNavigate();
  const upload = useUpload();
  const githubImport = useGitHubImport();

  const [mode, setMode] = useState<UploadMode>('file');

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: upload.selectFile,
    onDropRejected: upload.rejectFile,
    accept: ACCEPTED_ARCHIVE_TYPES,
    maxFiles: 1,
    multiple: false,
    noClick: false,
  });

  const handleAnalyseFile = async () => {
    const repository = await upload.analyseFile();
    if (repository) navigate(repository.status === 'completed' ? `/repositories/${repository.id}` : `/analysis/${repository.id}`);
  };

  const handleAnalyseGithub = async () => {
    const repository = await githubImport.analyseGithub();
    if (repository) navigate(repository.status === 'completed' ? `/repositories/${repository.id}` : `/analysis/${repository.id}`);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <PageHeader
        title="Upload Repository"
        description="Upload a repository archive or import from GitHub"
      >
        <DataSourceBadge source={mode === 'file' ? upload.source : githubImport.source} />
      </PageHeader>

      <div className="flex items-center gap-1 p-1 rounded-lg bg-muted mb-6 w-fit">
        <button
          onClick={() => { setMode('file'); githubImport.retry(); }}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all',
            mode === 'file'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <FileArchive className="h-4 w-4" />
          Upload File
        </button>
        <button
          onClick={() => { setMode('github'); upload.retry(); }}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all',
            mode === 'github'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Github className="h-4 w-4" />
          GitHub URL
        </button>
      </div>

      <AnimatePresence mode="wait">
        {mode === 'file' ? (
          <motion.div
            key="file"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            transition={{ duration: 0.2 }}
          >
            <div
              {...getRootProps()}
              className={cn(
                'relative rounded-xl border-2 border-dashed p-12 text-center cursor-pointer transition-all duration-200',
                isDragActive
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-muted-foreground/50 hover:bg-accent/30',
                upload.uploadFile && 'pointer-events-none opacity-50'
              )}
            >
              {/* react-dropzone renders a visually hidden file input. It is
                  still reachable programmatically and by assistive tech, so it
                  needs its own accessible name. */}
              <input {...getInputProps()} aria-label="Choose a repository archive to upload" />
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    'flex h-14 w-14 items-center justify-center rounded-2xl mb-4 transition-colors',
                    isDragActive ? 'bg-primary/10' : 'bg-muted'
                  )}
                >
                  <Upload
                    className={cn(
                      'h-6 w-6',
                      isDragActive ? 'text-primary' : 'text-muted-foreground'
                    )}
                  />
                </div>
                <p className="text-sm font-medium text-foreground mb-1">
                  {isDragActive
                    ? 'Drop your file here'
                    : 'Drag and drop your repository archive'}
                </p>
                <p className="text-xs text-muted-foreground mb-4">
                  Supports ZIP, TAR, TAR.GZ, and TGZ files up to {formatFileSize(MAX_FILE_SIZE)}
                </p>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); open(); }}
                  className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors"
                >
                  Browse Files
                </button>
              </div>
            </div>

            <AnimatePresence>
              {upload.error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-4 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-3"
                >
                  <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
                  <p className="text-sm text-destructive">{upload.error}</p>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {upload.uploadFile && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className="mt-4 rounded-xl border border-border bg-card p-4"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <File className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {upload.uploadFile.name}
                        </p>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <HardDrive className="h-3 w-3" />
                            {formatFileSize(upload.uploadFile.size)}
                          </span>
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Calendar className="h-3 w-3" />
                            {new Date(upload.uploadFile.lastModified).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={upload.removeFile}
                      className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {upload.uploadFile && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-6 flex justify-end"
              >
                <button
                  onClick={handleAnalyseFile}
                  disabled={upload.loading}
                  className="flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  {upload.loading ? 'Starting Analysis...' : 'Analyse Repository'}
                  <ArrowRight className="h-4 w-4" />
                </button>
              </motion.div>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="github"
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.2 }}
          >
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                  <Github className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Import from GitHub
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Paste a public repository URL
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                    Repository URL
                  </label>
                  <input
                    type="url"
                    value={githubImport.githubUrl}
                    onChange={(e) => githubImport.setGithubUrl(e.target.value)}
                    placeholder="https://github.com/owner/repository"
                    className="w-full rounded-md border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring font-mono"
                  />
                </div>

                <AnimatePresence>
                  {githubImport.error && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-3"
                    >
                      <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
                      <p className="text-sm text-destructive">{githubImport.error}</p>
                    </motion.div>
                  )}
                </AnimatePresence>

                {githubImport.previewName && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex items-center gap-2 rounded-lg border border-success/30 bg-success/5 px-4 py-3"
                  >
                    <div className="h-2 w-2 rounded-full bg-success" />
                    <p className="text-sm text-foreground">
                      Repository: <span className="font-medium">{githubImport.previewName}</span>
                    </p>
                  </motion.div>
                )}
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={handleAnalyseGithub}
                disabled={!githubImport.githubUrl.trim() || githubImport.loading}
                className={cn(
                  'flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors',
                  githubImport.githubUrl.trim() && !githubImport.loading
                    ? 'hover:bg-primary/90'
                    : 'opacity-50 cursor-not-allowed'
                )}
              >
                {githubImport.loading ? 'Starting Analysis...' : 'Analyse Repository'}
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
