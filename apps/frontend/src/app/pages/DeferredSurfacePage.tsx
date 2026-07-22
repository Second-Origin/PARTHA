import { useNavigate } from 'react-router-dom';
import { CircleDashed } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import type { DeferredProductSurface } from '@/app/routes/productSurfaces';

function phaseDescription(phase: DeferredProductSurface['phase']): string {
  return phase === 'not-scheduled'
    ? 'This surface is not scheduled for a delivery phase.'
    : `This surface is deferred until Phase ${phase} work is ready.`;
}

export function DeferredSurfacePage({ surface }: { surface: DeferredProductSurface }) {
  const navigate = useNavigate();
  const blockingIssues = surface.blockingIssues.map((issue) => `#${issue}`).join(' and ');

  return (
    <div>
      <PageHeader title={surface.label} description="This product surface is deferred behind its roadmap gate." />
      <EmptyState
        icon={CircleDashed}
        title={`${surface.label} is not available in the current delivery phase.`}
        description={`${phaseDescription(surface.phase)} Blocking work: ${blockingIssues}.`}
        action={{ label: 'Back to Dashboard', onClick: () => navigate('/') }}
      />
    </div>
  );
}
