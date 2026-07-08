import { AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { ReviewFinding } from '@/shared/types/review';

interface FindingCardProps {
  finding: ReviewFinding;
  isSelected: boolean;
  onClick: () => void;
}

const severityConfig = {
  critical: { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20', dot: 'bg-red-400' },
  high: { icon: AlertCircle, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20', dot: 'bg-orange-400' },
  medium: { icon: Info, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20', dot: 'bg-amber-400' },
  low: { icon: CheckCircle2, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20', dot: 'bg-blue-400' },
};

export function FindingCard({ finding, isSelected, onClick }: FindingCardProps) {
  const config = severityConfig[finding.severity];
  const Icon = config.icon;

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full rounded-lg border p-4 text-left transition-all',
        isSelected ? 'border-primary/50 bg-primary/5 shadow-sm' : 'border-border bg-card hover:border-primary/20 hover:shadow-sm'
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', config.bg)}>
          <Icon className={cn('h-4 w-4', config.color)} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-sm font-medium text-foreground truncate">{finding.title}</p>
          </div>
          <p className="text-xs text-muted-foreground line-clamp-2">{finding.problem}</p>
          <div className="flex items-center gap-2 mt-2">
            <span className={cn('inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium border', config.bg)}>
              <span className={cn('h-1.5 w-1.5 rounded-full', config.dot)} />
              {finding.severity}
            </span>
            <span className="text-[10px] text-muted-foreground capitalize px-1.5 py-0.5 rounded-md bg-muted">
              {finding.category.replace('-', ' ')}
            </span>
            <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 rounded-md bg-muted capitalize">
              {finding.estimatedEffort}
            </span>
          </div>
        </div>
      </div>
    </button>
  );
}
