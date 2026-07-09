import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GitBranch, Package, Search } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { ExportMenu } from '@/shared/components/ui/ExportMenu';
import { useDependencies } from '@/features/dependencies/hooks/useDependencies';

export function DependenciesPage() {
  const navigate = useNavigate();
  const dependencies = useDependencies();
  const activeRepository = dependencies.activeRepository;
  const [query, setQuery] = useState('');

  const filteredNodes = useMemo(() => {
    const q = query.trim().toLowerCase();
    const nodes = dependencies.graph?.nodes || [];
    if (!q) return nodes;
    return nodes.filter((node) => node.name.toLowerCase().includes(q) || node.type.toLowerCase().includes(q));
  }, [dependencies.graph?.nodes, query]);


  if (dependencies.emptyReason === 'no-completed-repositories') {
    return (
      <div>
        <PageHeader title="Dependency Graph" description="Explore the dependency relationships within your codebase" />
        <EmptyState
          icon={GitBranch}
          title="No dependency data"
          description="Upload and analyse a repository to view its dependency graph. Dependencies are extracted during the analysis pipeline."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (dependencies.emptyReason === 'no-active-repository' || !activeRepository) {
    return (
      <div>
        <PageHeader title="Dependency Graph" description="Explore the dependency relationships within your codebase" />
        <EmptyState
          icon={GitBranch}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to explore its dependencies."
        />
      </div>
    );
  }

  if (dependencies.loading) {
    return (
      <div>
        <PageHeader title="Dependency Graph" description={`Dependencies for ${activeRepository.name}`}>
          <DataSourceBadge source={dependencies.source} />
        </PageHeader>
        <div className="rounded-xl border border-border bg-card p-8 text-sm text-muted-foreground">Loading dependency graph...</div>
      </div>
    );
  }

  if (dependencies.error) {
    return (
      <div>
        <PageHeader title="Dependency Graph" description={`Dependencies for ${activeRepository.name}`}>
          <DataSourceBadge source={dependencies.source} />
        </PageHeader>
        <div className="rounded-xl border border-destructive/50 bg-destructive/5 p-5">
          <p className="text-sm text-destructive">{dependencies.error}</p>
          <button onClick={dependencies.retry} className="mt-3 text-xs text-primary hover:underline">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Dependency Graph" description={`Dependencies for ${activeRepository.name}`}>
        <DataSourceBadge source={dependencies.source} />
      </PageHeader>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
        <Stat label="Dependencies" value={dependencies.graph?.totalDependencies ?? 0} />
        <Stat label="Relations" value={dependencies.graph?.edges.length ?? 0} />
        <Stat label="Vulnerable" value={dependencies.graph?.vulnerabilities ?? 0} />
        <Stat label="Outdated" value={dependencies.graph?.outdated ?? 0} />
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="relative max-w-sm flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search dependencies..."
              className="w-full rounded-md border border-border bg-background pl-8 pr-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <ExportMenu repositoryId={activeRepository.id} target="dependencies" disabled={!dependencies.graph} />
        </div>
        {filteredNodes.length === 0 ? (
          <div className="p-8 text-center">
            <GitBranch className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">No dependencies matched your search.</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredNodes.map((node) => (
              <div key={node.id} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
                    <Package className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{node.name}</p>
                    <p className="text-xs text-muted-foreground">{node.version || 'unknown version'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground capitalize">{node.type}</span>
                  {node.hasVulnerabilities && <span className="rounded-md bg-destructive/10 px-2 py-0.5 text-xs text-destructive">vulnerable</span>}
                  {node.isOutdated && <span className="rounded-md bg-warning/10 px-2 py-0.5 text-xs text-warning">outdated</span>}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
          {dependencies.packageManager} detected. Dependency relationships are generated from backend package manifests.
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}
