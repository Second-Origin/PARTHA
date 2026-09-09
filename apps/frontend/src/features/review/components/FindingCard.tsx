import { AlertTriangle, AlertCircle, Info, CheckCircle2, FileCode } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { ReviewFinding } from '@/shared/types/review';

interface FindingCardProps {
  finding: ReviewFinding;
  isSelected: boolean;
  onClick: () => void;
}

const severityConfig = {
  critical: { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
  high: { icon: AlertCircle, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20' },
  medium: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
  low: { icon: CheckCircle2, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
  info: { icon: Info, color: 'text-slate-400', bg: 'bg-slate-500/10 border-slate-500/20' },
};

export function FindingCard({ finding, isSelected, onClick }: FindingCardProps) {
  const config = severityConfig[finding.severity];
  const Icon = config.icon;
  const span =
    finding.startLine === finding.endLine
      ? `${finding.startLine}`
      : `${finding.startLine}-${finding.endLine}`;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isSelected}
      className={cn(
        'w-full rounded-lg border p-4 text-left transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary',
        isSelected
          ? 'border-primary/50 bg-primary/5 shadow-sm'
          : 'border-border bg-card hover:border-primary/20 hover:shadow-sm',
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border', config.bg)}>
          <Icon className={cn('h-4 w-4', config.color)} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-foreground">{finding.title}</p>
            <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium uppercase', config.bg, config.color)}>
              {finding.severity}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{finding.explanation}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
            <span className="rounded bg-muted px-1.5 py-0.5">
              {finding.category.replace(/_/g, ' ')}
            </span>
            <span className="inline-flex items-center gap-1 font-mono">
              <FileCode className="h-3 w-3" />
              {finding.path}:{span}
            </span>
            <span>{finding.diagnosticCode}</span>
          </div>
        </div>
      </div>
    </button>
  );
}
