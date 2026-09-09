import brandLogo from '../../../../../../docs/assets/Partha-logo v1.svg';
import { cn } from '@/shared/utils/cn';

interface BrandLogoProps {
  className?: string;
  compact?: boolean;
}

/** Reuses the designer-supplied PARTHA mark; no substitute glyphs or generated logo. */
export function BrandLogo({ className, compact = false }: BrandLogoProps) {
  return (
    <span className={cn('block overflow-hidden', compact ? 'w-9' : 'w-[132px]', className)}>
      <img
        src={brandLogo}
        alt="PARTHA"
        className="h-auto w-[132px] max-w-none"
      />
    </span>
  );
}
