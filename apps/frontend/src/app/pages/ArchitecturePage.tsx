import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ExternalLink, Network, ShieldCheck } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { ExportMenu } from '@/shared/components/ui/ExportMenu';
import { ArchWorkspace } from '@/features/architecture/components/ArchWorkspace';
import { AuthenticationExplanationPanel } from '@/features/architecture/components/AuthenticationExplanationPanel';
import { RevisionManifestPanel } from '@/features/architecture/components/RevisionManifestPanel';
import { useArchitecture } from '@/features/architecture/hooks/useArchitecture';

export function ArchitecturePage() {
  const navigate = useNavigate();
  const architecture = useArchitecture();
  const [authPanelOpen, setAuthPanelOpen] = useState(false);

  if (architecture.emptyReason === 'no-completed-repositories') {
    return (
      <div className="h-full flex flex-col">
        <PageHeader title="Architecture" description="Explore the architecture of your codebase" />
        <EmptyState
          icon={Network}
          title="No architecture data"
          description="Upload and analyse a repository to generate its architecture model. The architecture graph is built during the analysis pipeline."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (architecture.emptyReason === 'no-active-repository') {
    return (
      <div className="h-full flex flex-col">
        <PageHeader title="Architecture" description="Explore the architecture of your codebase" />
        <EmptyState
          icon={Network}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to explore its architecture."
        />
      </div>
    );
  }

  if (architecture.loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span className="text-sm text-muted-foreground">Loading architecture model...</span>
        </div>
      </div>
    );
  }

  // A repository can be analysed yet still have no sealed ri.v1 snapshot
  // (#217, same 404 contract as Dependencies/Review/Insights). That must read
  // as "run analysis again", never as a silent, indistinguishable empty graph.
  if (architecture.noSnapshot) {
    return (
      <div className="h-full flex flex-col">
        <PageHeader title="Architecture" description="Explore the architecture of your codebase" />
        <EmptyState
          icon={Network}
          title="No sealed snapshot yet"
          description="This repository has no sealed Repository Intelligence snapshot for its current revision. Analyse it again to generate one."
          action={{ label: 'Run analysis', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (architecture.error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-destructive mb-2">{architecture.error}</p>
          <button
            onClick={architecture.retry}
            className="text-xs text-primary hover:underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!architecture.model) {
    return null;
  }

  return (
    <div className="h-[calc(100vh-8rem)] -m-6 flex flex-col">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3 sm:px-6">
        <h1 className="min-w-0 truncate text-sm font-medium text-foreground">Architecture - {architecture.model.repositoryName}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/review"
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-accent/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            Engineering Review
            <ExternalLink className="h-3 w-3" />
          </Link>
          <button
            type="button"
            onClick={() => setAuthPanelOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-accent/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Explain Authentication
          </button>
          <ExportMenu repositoryId={architecture.model.repositoryId} target="architecture" label="Export Report" />
        </div>
      </div>
      {/* The manifest names the exact revision every citation below belongs
          to, so it sits with the evidence rather than in a settings page. */}
      <div className="mb-4">
        <RevisionManifestPanel repositoryId={architecture.model.repositoryId} />
      </div>
      <div className="flex-1 min-h-0">
        <ArchWorkspace model={architecture.model} source={architecture.source} />
      </div>
      <AuthenticationExplanationPanel open={authPanelOpen} onClose={() => setAuthPanelOpen(false)} />
    </div>
  );
}
