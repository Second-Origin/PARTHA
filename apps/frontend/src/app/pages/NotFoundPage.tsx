import { useNavigate } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { PageHeader } from '@/shared/components/ui/PageHeader';

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader title="Page not found" />
      <EmptyState
        icon={Compass}
        title="This page doesn't exist"
        description="The link may be out of date, or the page may have moved."
        action={{ label: 'Back to Dashboard', onClick: () => navigate('/') }}
      />
    </div>
  );
}
