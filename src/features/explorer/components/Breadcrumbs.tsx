import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/utils/cn';

interface BreadcrumbsProps {
  path: string;
  onNavigate?: (path: string) => void;
}

export function Breadcrumbs({ path, onNavigate }: BreadcrumbsProps) {
  const segments = path.split('/').filter(Boolean);

  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground overflow-x-auto scrollbar-thin">
      <button
        onClick={() => onNavigate?.('/')}
        className="flex items-center gap-1 hover:text-foreground transition-colors shrink-0"
      >
        <Home className="h-3 w-3" />
      </button>
      {segments.map((segment, i) => {
        const fullPath = '/' + segments.slice(0, i + 1).join('/');
        const isLast = i === segments.length - 1;
        return (
          <div key={fullPath} className="flex items-center gap-1 shrink-0">
            <ChevronRight className="h-3 w-3 text-muted-foreground/50" />
            <button
              onClick={() => !isLast && onNavigate?.(fullPath)}
              className={cn(
                'transition-colors',
                isLast ? 'text-foreground font-medium' : 'hover:text-foreground'
              )}
            >
              {segment}
            </button>
          </div>
        );
      })}
    </div>
  );
}
