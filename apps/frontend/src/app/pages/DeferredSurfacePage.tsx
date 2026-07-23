import { useNavigate } from 'react-router-dom';
import { CircleDashed } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import type { DeferredProductSurface } from '@/app/routes/productSurfaces';

export function DeferredSurfacePage({ surface }: { surface: DeferredProductSurface }) {
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader title={surface.label} />
      <EmptyState
        icon={CircleDashed}
        title={`${surface.label} isn't available yet.`}
        description={surface.unavailableMessage}
        action={{ label: 'Back to Dashboard', onClick: () => navigate('/') }}
      />
    </div>
  );
}
