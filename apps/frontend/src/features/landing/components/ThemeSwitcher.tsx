import { Monitor, Moon, Sun } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { LandingThemePreference } from '../hooks/useLandingTheme';

interface ThemeSwitcherProps {
  preference: LandingThemePreference;
  onChange: (preference: LandingThemePreference) => void;
  className?: string;
}

const OPTIONS: { value: LandingThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'system', label: 'System', icon: Monitor },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
];

/** Restyled, icon-only variant of the Settings > Appearance radiogroup
 * pattern -- same interaction model, but matched to the flat black/white/
 * orange landing palette from the Figma dark-mode reference rather than
 * the app's card/border tokens. */
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
          className={cn(
            'flex h-7 w-7 items-center justify-center rounded-full transition-colors',
            preference === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}
