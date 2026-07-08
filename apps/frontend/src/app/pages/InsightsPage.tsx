import { useNavigate } from 'react-router-dom';
import { Lightbulb, Lock } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { useInsights } from '@/features/insights/hooks/useInsights';

export function InsightsPage() {
  const navigate = useNavigate();
  const insights = useInsights();
  const activeRepository = insights.activeRepository;

  if (insights.emptyReason === 'no-completed-repositories') {
    return (
      <div>
        <PageHeader title="Insights" description="Code quality insights and recommendations" />
        <EmptyState
          icon={Lightbulb}
          title="No insights available"
          description="Upload and analyse a repository first. Insights are generated from a completed analysis pipeline."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (insights.emptyReason === 'no-active-repository' || !activeRepository) {
    return (
      <div>
        <PageHeader title="Insights" description="Code quality insights and recommendations" />
        <EmptyState
          icon={Lightbulb}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to view code insights."
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Insights" description={`Insights for ${activeRepository.name}`}>
        <DataSourceBadge source={insights.source} />
      </PageHeader>
      <div className="rounded-xl border border-border bg-card p-8 min-h-[400px] flex flex-col items-center justify-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted mb-5">
          <Lock className="h-7 w-7 text-muted-foreground" />
        </div>
        <h3 className="text-base font-medium text-foreground mb-2">Code Insights Coming Soon</h3>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          Repository <span className="font-medium text-foreground">{activeRepository.name}</span> is ready for insight generation.
          This workflow is intentionally disabled until the insights endpoint is implemented.
        </p>
      </div>
    </div>
  );
}
