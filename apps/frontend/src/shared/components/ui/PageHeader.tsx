import { cn } from '@/shared/utils/cn';

interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, description, children, className }: PageHeaderProps) {
  return (
    <div className={cn('mb-6 flex min-w-0 flex-col items-start justify-between gap-4 sm:flex-row sm:items-start', className)}>
      <div className="min-w-0">
        <h1 className="partha-heading break-words text-2xl leading-8">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-base text-muted-foreground">{description}</p>}
      </div>
      {children && <div className="flex max-w-full flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}
