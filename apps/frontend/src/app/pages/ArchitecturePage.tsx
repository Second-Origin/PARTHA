import { useNavigate } from 'react-router-dom';
import { Network } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { ArchWorkspace } from '@/features/architecture/components/ArchWorkspace';
import { useArchitecture } from '@/features/architecture/hooks/useArchitecture';

export function ArchitecturePage() {
  const navigate = useNavigate();
  const architecture = useArchitecture();

  if (architecture.emptyReason === 'no-completed-repositories') {
    return (
      <div className="h-full flex flex-col">
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
        <EmptyState
          icon={Network}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to explore its architecture."
        />
      </div>
    );
  }

  if (!architecture.model) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          {architecture.loading && (
            <>
              <div className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <span className="text-sm text-muted-foreground">Loading architecture model...</span>
            </>
          )}
          {architecture.error && (
            <div className="text-center">
              <p className="text-sm text-destructive mb-2">{architecture.error}</p>
              <button
                onClick={architecture.retry}
                className="text-xs text-primary hover:underline"
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-8rem)] -m-6 flex flex-col">
      <ArchWorkspace model={architecture.model} source={architecture.source} />
    </div>
  );
}
