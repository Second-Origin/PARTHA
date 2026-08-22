import { cn } from '@/shared/utils/cn';

interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, description, children, className }: PageHeaderProps) {
  return (
    <div className={cn('mb-8 flex min-w-0 flex-col items-start justify-between gap-4 border-b border-primary/20 pb-6 sm:flex-row sm:items-end', className)}>
      <div className="min-w-0">
        <p className="mb-2 text-xs font-medium uppercase tracking-[0.16em] text-primary">Repository intelligence</p>
        <h1 className="break-words text-3xl font-medium tracking-[-0.055em] text-foreground sm:text-4xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">{description}</p>}
      </div>
      {children && <div className="flex max-w-full flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}
