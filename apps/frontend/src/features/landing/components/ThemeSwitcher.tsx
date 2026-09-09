import { Laptop, Moon, Sun } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { LandingThemePreference } from '../hooks/useLandingTheme';

interface ThemeSwitcherProps {
  preference: LandingThemePreference;
  onChange: (preference: LandingThemePreference) => void;
  className?: string;
}

const OPTIONS: { value: LandingThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'system', label: 'System', icon: Laptop },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
];

/** Traced directly from the Figma dark-mode reference's footer artwork
 * (Container-PARTHA-product.svg): a flat pill with a 1px --primary border
 * and three uniformly --muted-foreground icons. The reference art has no
 * active/selected-state treatment at all -- no fill, no highlight -- so
 * this doesn't add one either. aria-checked is still set correctly on the
 * selected option: that's a semantic attribute for assistive tech, not a
 * visual element, and leaving it out would be an accessibility regression
 * the reference (a static image) has no opinion on either way. */
export function ThemeSwitcher({ preference, onChange, className }: ThemeSwitcherProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={cn('inline-flex items-center gap-1 rounded-full border border-primary p-1', className)}
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={preference === value}
          aria-label={label}
          onClick={() => onChange(value)}
          className="flex h-7 w-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
        >
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}
