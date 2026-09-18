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
    <div className={cn('partha-surface min-w-0 px-4 pb-4 pt-[17px]', className)}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <span className="text-[15px] font-medium uppercase leading-5 tracking-[0.08em] text-foreground">{label}</span>
        <Icon aria-hidden="true" className="h-4 w-4 shrink-0 text-white" />
      </div>
      <div className="flex items-end gap-2">
        <span className="font-display text-[26px] font-semibold leading-8 text-foreground">{value}</span>
        {change && <span className="text-xs text-success mb-0.5">{change}</span>}
      </div>
    </div>
  );
}
