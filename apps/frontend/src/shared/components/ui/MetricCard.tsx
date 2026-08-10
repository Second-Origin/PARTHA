import { cn } from '@/shared/utils/cn';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  change?: string;
  className?: string;
}

export function MetricCard({ label, value, icon: Icon, change, className }: MetricCardProps) {
  return (
    <div className={cn('partha-surface min-w-0 p-4', className)}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</span>
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </span>
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-semibold text-foreground">{value}</span>
        {change && <span className="text-xs text-success mb-0.5">{change}</span>}
      </div>
    </div>
  );
}
