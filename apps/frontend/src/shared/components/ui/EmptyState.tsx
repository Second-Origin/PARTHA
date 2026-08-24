import { motion } from 'framer-motion';
import { cn } from '@/shared/utils/cn';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className={cn('flex flex-col items-center justify-center rounded-3xl border border-primary/15 bg-card/60 px-4 py-16', className)}
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/15 bg-secondary">
        <Icon className="h-7 w-7 text-muted-foreground" />
      </div>
      {/* Sits directly beneath the page's h1, so it must be h2: skipping a
          level breaks heading navigation for screen-reader users. */}
      <h2 className="text-lg font-semibold text-foreground mb-1">{title}</h2>
      <p className="text-sm text-muted-foreground text-center max-w-sm mb-6">{description}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_hsl(var(--primary)/0.18)] hover:bg-primary/90 transition-colors"
        >
          {action.label}
        </button>
      )}
    </motion.div>
  );
}
