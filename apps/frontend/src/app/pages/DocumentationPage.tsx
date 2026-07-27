import { useNavigate } from 'react-router-dom';
import { FileText, RefreshCw } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { ExportMenu } from '@/shared/components/ui/ExportMenu';
import { useDocumentation } from '@/features/documentation/hooks/useDocumentation';

export function DocumentationPage() {
  const navigate = useNavigate();
  const documentation = useDocumentation();
  const activeRepository = documentation.activeRepository;
  const sections = [
    ['overview', 'Overview'],
    ['architecture', 'Architecture'],
    ['folder-structure', 'Folder structure'],
    ['api', 'API'],
    ['environment', 'Environment'],
    ['deployment', 'Deployment'],
    ['contribution', 'Contribution'],
  ] as const;


  if (documentation.emptyReason === 'no-completed-repositories') {
    return (
      <div>
        <PageHeader title="Documentation" description="Auto-generated documentation from your codebase" />
        <EmptyState
          icon={FileText}
          title="No documentation generated"
          description="Upload and analyse a repository first. Documentation generation requires a completed analysis pipeline."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (documentation.emptyReason === 'no-active-repository' || !activeRepository) {
    return (
      <div>
        <PageHeader title="Documentation" description="Auto-generated documentation from your codebase" />
        <EmptyState
          icon={FileText}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to view generated documentation."
        />
      </div>
    );
  }

  // A repository can be analysed yet still have no sealed ri.v1 snapshot
  // (#178, same 404 contract as Dependencies/Architecture). That must read as
  // "run analysis again", never as a generic, unguided error message.
  if (documentation.noSnapshot) {
    return (
      <div>
        <PageHeader title="Documentation" description="Auto-generated documentation from your codebase" />
        <EmptyState
          icon={FileText}
          title="No sealed snapshot yet"
          description="This repository has no sealed Repository Intelligence snapshot for its current revision. Analyse it again to generate one."
          action={{ label: 'Run analysis', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Documentation" description={`Documentation for ${activeRepository.name}`}>
        <DataSourceBadge source={documentation.source} />
      </PageHeader>
      {documentation.document && (
        <p className="text-xs text-muted-foreground">
          Sealed {documentation.document.snapshotSchemaVersion} snapshot{' '}
          <span className="font-mono">{documentation.document.snapshotId}</span> · revision{' '}
          <span className="font-mono">{documentation.document.revisionValue}</span>
        </p>
      )}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-border px-4 py-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => documentation.setFormat('markdown')}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${documentation.format === 'markdown' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'}`}
              >
                Markdown
              </button>
              <button
                onClick={() => documentation.setFormat('html')}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${documentation.format === 'html' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'}`}
              >
                HTML
              </button>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={documentation.refresh} className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-accent transition-colors">
                <RefreshCw className="h-3.5 w-3.5" /> Regenerate
              </button>
              <ExportMenu repositoryId={activeRepository.id} target="documentation" disabled={!documentation.document} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {sections.map(([id, label]) => (
              <button
                key={id}
                onClick={() => documentation.toggleSection(id)}
                className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${documentation.sections.includes(id) ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {documentation.loading ? (
          <div className="p-8 text-sm text-muted-foreground">Generating documentation...</div>
        ) : documentation.error ? (
          <div className="p-8">
            <p className="text-sm text-destructive">{documentation.error}</p>
            <button onClick={documentation.retry} className="mt-3 text-xs text-primary hover:underline">Retry</button>
          </div>
        ) : (
          <pre className="max-h-[620px] overflow-auto whitespace-pre-wrap p-5 text-sm leading-6 text-foreground font-mono scrollbar-thin">
            {documentation.document?.content || 'No documentation generated.'}
          </pre>
        )}
      </div>
    </div>
  );
}
