import { useNavigate } from 'react-router-dom';
import { Download, FileText, RefreshCw } from 'lucide-react';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { DataSourceBadge } from '@/components/shared/DataSourceBadge';
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

  const exportDocument = () => {
    if (!documentation.document || !activeRepository) return;
    const extension = documentation.document.format === 'html' ? 'html' : 'md';
    const type = documentation.document.format === 'html' ? 'text/html' : 'text/markdown';
    const blob = new Blob([documentation.document.content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${activeRepository.name}-documentation.${extension}`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

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

  return (
    <div>
      <PageHeader title="Documentation" description={`Documentation for ${activeRepository.name}`}>
        <DataSourceBadge source={documentation.source} />
      </PageHeader>
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
              <button onClick={exportDocument} disabled={!documentation.document} className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                <Download className="h-3.5 w-3.5" /> Export
              </button>
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
