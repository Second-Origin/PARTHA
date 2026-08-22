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
    <div className={cn('partha-surface min-w-0 border-primary/35 p-5', className)}>
      <div className="mb-5 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">{label}</span>
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </span>
      </div>
      <div className="flex items-end gap-2">
        <span className="text-3xl font-medium tracking-[-0.05em] text-foreground">{value}</span>
        {change && <span className="text-xs text-success mb-0.5">{change}</span>}
      </div>
    </div>
  );
}
