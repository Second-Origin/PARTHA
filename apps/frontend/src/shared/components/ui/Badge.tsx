import { cn } from '@/shared/utils/cn';

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info';

const variants: Record<BadgeVariant, string> = {
  default: 'bg-muted text-muted-foreground',
  success: 'bg-[hsl(142_100%_45%/0.1)] text-success',
  warning: 'bg-warning/10 text-warning',
  // Text shades sit a step darker than the tokens so each pill still clears
  // AA on its own tint over the #F2E1D5 cards.
  error: 'bg-destructive/10 text-[hsl(0_74%_36%)]',
  info: 'bg-primary/10 text-[hsl(22_100%_26%)]',
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-sm', variants[variant], className)}>
      {children}
    </span>
  );
}
