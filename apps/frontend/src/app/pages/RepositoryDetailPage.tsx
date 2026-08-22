import { useMemo } from 'react';
import { Navigate, useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { parseEvidenceCitation } from '@/features/explorer/fileUtils';
import {
  ArrowLeft,
  FolderGit2,
  Clock,
  FileCode,
  Globe,
  Upload as UploadIcon,
  Code2,
  Package,
  FileText,
  Scale,
  Settings2,
  FolderTree,
  GitBranch,
  GitCommitHorizontal,
  Fingerprint,
  Layers,
} from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { Badge } from '@/shared/components/ui/Badge';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { RepositoryExplorer } from '@/features/explorer/components/RepositoryExplorer';
import { RepositoryOutcomeSummary } from '@/features/repositories/components/RepositoryOutcomeSummary';
import { useRepositoryDetail } from '@/features/repositories/hooks/useRepositoryDetail';
import { useRepositoryTree } from '@/features/repositories/hooks/useRepositoryTree';
import { repositoryStatusVariant } from '@/features/repositories/status';
import { formatFileSize } from '@/shared/utils/cn';
import { cn } from '@/shared/utils/cn';

export function RepositoryDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { repository: repo, tabs, activeTab, setActiveTab, redirectToAnalysis } = useRepositoryDetail(id);
  const repositoryTree = useRepositoryTree(repo);

  const citation = useMemo(() => parseEvidenceCitation(searchParams), [searchParams]);
  const initialFilePath = searchParams.get('path');

  if (!repo) {
    return (
      <div>
        <button
          onClick={() => navigate('/repositories')}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Repositories
        </button>
        <EmptyState
          icon={FolderGit2}
          title="Repository not found"
          description="The repository you're looking for doesn't exist or has been removed."
          action={{ label: 'View All Repositories', onClick: () => navigate('/repositories') }}
        />
      </div>
    );
  }

  if (redirectToAnalysis) {
    return <Navigate to={redirectToAnalysis} replace />;
  }

  return (
    <div>
      <button
        onClick={() => navigate('/repositories')}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Repositories
      </button>
      <PageHeader title={repo.name} description={repo.description || `${repo.source === 'github' ? 'Imported from GitHub' : 'Uploaded archive'}`}>
        <DataSourceBadge source={repositoryTree.source} />
        <Badge variant={repositoryStatusVariant[repo.status]}>{repo.status}</Badge>
      </PageHeader>

      {repo.status === 'error' ? (
        <div className="rounded-xl border border-destructive/50 bg-destructive/5 p-6">
          <p className="text-sm text-destructive">{repo.errorMessage || 'An error occurred during analysis.'}</p>
          <button
            onClick={() => navigate('/upload')}
            className="mt-3 text-sm text-primary hover:underline"
          >
            Try uploading again
          </button>
        </div>
      ) : repo.status === 'completed' && repo.meta ? (
        <>
          <RepositoryOutcomeSummary repository={repo} />

          <div className="mb-6 flex items-center gap-1 border-b border-[#fa4d01]/15">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={cn(
                  'relative rounded-t-xl px-4 py-3 text-sm font-semibold transition-colors',
                  activeTab === tab ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {tab}
                {activeTab === tab && (
                  <motion.div
                    layoutId="repo-tab"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full"
                  />
                )}
              </button>
            ))}
          </div>

          {activeTab === 'Overview' && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <InfoCard icon={Code2} label="Language" value={repo.meta.language} />
                <InfoCard icon={Layers} label="Framework" value={repo.meta.framework} />
                <InfoCard icon={FileCode} label="Files" value={String(repo.meta.totalFiles)} />
                <InfoCard icon={FolderTree} label="Folders" value={String(repo.meta.totalFolders)} />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="rounded-3xl border border-[#fa4d01]/20 bg-card p-6 shadow-[0_14px_34px_rgba(48,21,47,0.04)]">
                  <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-primary">Repository</p><h2 className="mt-1 text-lg font-semibold text-foreground mb-4">Repository Information</h2>
                  <div className="space-y-3">
                    <InfoRow icon={FolderGit2} label="Name" value={repo.name} />
                    <InfoRow
                      icon={repo.source === 'github' ? Globe : UploadIcon}
                      label="Source"
                      value={repo.source === 'github' ? 'GitHub' : 'File Upload'}
                    />
                    {repo.sourceUrl && (
                      <InfoRow icon={Globe} label="URL" value={repo.sourceUrl} mono />
                    )}
                    <InfoRow icon={Clock} label="Uploaded" value={new Date(repo.uploadedAt).toLocaleString()} />
                    {repo.analysedAt && (
                      <InfoRow icon={Clock} label="Analysed" value={new Date(repo.analysedAt).toLocaleString()} />
                    )}
                    {/* The exact source this repository was analysed at (#87). Shown in
                        full, not abbreviated: this is the page you open to answer
                        "which code is this?", and a shortened prefix is not an identity. */}
                    {repo.revision && (
                      <InfoRow
                        icon={repo.revision.kind === 'git' ? GitCommitHorizontal : Fingerprint}
                        label={repo.revision.kind === 'git' ? 'Commit' : 'Content hash'}
                        value={repo.revision.value}
                        mono
                      />
                    )}
                    {repo.revision?.ref && (
                      <InfoRow
                        icon={GitBranch}
                        label="Branch"
                        value={repo.revision.ref.replace(/^refs\/heads\//, '')}
                        mono
                      />
                    )}
                    {repo.size > 0 && (
                      <InfoRow icon={Package} label="Size" value={formatFileSize(repo.size)} />
                    )}
                  </div>
                </div>

                <div className="rounded-3xl border border-[#fa4d01]/20 bg-card p-6 shadow-[0_14px_34px_rgba(48,21,47,0.04)]">
                  <p className="text-2xs font-semibold uppercase tracking-[0.14em] text-primary">Evidence</p><h2 className="mt-1 text-lg font-semibold text-foreground mb-4">Detected Configuration</h2>
                  <div className="space-y-3">
                    {repo.meta.entryPoint && (
                      <InfoRow icon={FileCode} label="Entry Point" value={repo.meta.entryPoint} mono />
                    )}
                    {repo.meta.packageManager && (
                      <InfoRow icon={Package} label="Package Manager" value={repo.meta.packageManager} />
                    )}
                    <InfoRow
                      icon={FileText}
                      label="README"
                      value={repo.meta.hasReadme ? 'Found' : 'Not found'}
                    />
                    <InfoRow
                      icon={Scale}
                      label="License"
                      value={repo.meta.licenseName || 'None detected'}
                    />
                  </div>
                  {repo.meta.configFiles.length > 0 && (
                    <div className="mt-4 border-t border-[#fa4d01]/15 pt-4">
                      <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
                        <Settings2 className="h-3.5 w-3.5" />
                        Configuration Files
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {repo.meta.configFiles.map((file) => (
                          <span
                            key={file}
                            className="inline-flex items-center rounded-lg bg-[#fff1e9] px-2.5 py-1 text-xs font-mono text-muted-foreground"
                          >
                            {file}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'Explorer' && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <RepositoryExplorer
                fileTree={repositoryTree.fileTree}
                repositoryId={repo.id}
                initialPath={initialFilePath}
                citation={citation}
              />
            </motion.div>
          )}
        </>
      ) : null}
    </div>
  );
}

function InfoCard({ icon: Icon, label, value }: { icon: typeof Code2; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[#fa4d01]/20 bg-card p-4 shadow-[0_10px_24px_rgba(48,21,47,0.03)]">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <span className="text-2xs font-semibold text-primary uppercase tracking-[0.12em]">{label}</span>
      </div>
      <p className="text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function InfoRow({ icon: Icon, label, value, mono }: { icon: typeof Code2; label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      <span className={cn('text-sm text-foreground', mono && 'font-mono text-xs')}>{value}</span>
    </div>
  );
}
