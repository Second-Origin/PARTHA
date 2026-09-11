import imgMonitor from '@/assets/landing/figma/vector14.svg';
import imgMoon from '@/assets/landing/figma/vector12.svg';
import imgSun from '@/assets/landing/figma/vector13.svg';
import imgMonitorActive from '@/assets/landing/theme-vector14-active.svg';
import imgMoonActive from '@/assets/landing/theme-vector12-active.svg';
import imgSunActive from '@/assets/landing/theme-vector13-active.svg';
import { useLandingTheme, type LandingThemePreference } from '@/hooks/useLandingTheme';

/* The footer theme switch (Figma node 516:857): monitor, sun, moon in one
 * orange-outlined pill. The prototype uses it to flip the whole page between
 * the light and dark frames.
 *
 * The selected option is lit, not just opaque -- in the recording its glyph
 * turns Signal Orange and a soft round peach glow appears behind it, while the
 * other two stay grey. The glyphs are flat #7A7A7A fills with no currentColor
 * to hook into, so each one carries an orange twin and the pair is swapped.
 *
 * Insets are the design's own, so the icons sit exactly where they were drawn. */
const OPTIONS: {
  preference: LandingThemePreference;
  icon: string;
  iconActive: string;
  label: string;
  inset: string;
}[] = [
  {
    preference: 'system',
    icon: imgMonitor,
    iconActive: imgMonitorActive,
    label: 'Match system appearance',
    inset: 'inset-[28.95%_75.57%_28.95%_9.16%]',
  },
  {
    preference: 'light',
    icon: imgSun,
    iconActive: imgSunActive,
    label: 'Light appearance',
    inset: 'inset-[23.68%_41.98%_23.68%_42.75%]',
  },
  {
    preference: 'dark',
    icon: imgMoon,
    iconActive: imgMoonActive,
    label: 'Dark appearance',
    inset: 'inset-[23.68%_9.16%_23.68%_75.57%]',
  },
];

export function ThemeControl({ className }: { className?: string }) {
  const { preference, setPreference } = useLandingTheme();

  return (
    <div className={className} data-node-id="516:857" data-name="theme" role="group" aria-label="Appearance">
      <div className="absolute inset-0 rounded-[20px] border border-solid border-[#fa4d01]" />
      {OPTIONS.map((option) => {
        const active = preference === option.preference;
        return (
          <button
            key={option.preference}
            type="button"
            aria-label={option.label}
            aria-pressed={active}
            onClick={() => setPreference(option.preference)}
            className={`absolute block cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#fa4d01] ${option.inset}`}
          >
            {/* The glow sits behind the glyph and is wider than it, so it
                reads as light spilling out rather than a chip behind it. */}
            <span
              aria-hidden
              className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full transition-opacity duration-200 motion-reduce:transition-none"
              style={{
                width: 30,
                height: 30,
                opacity: active ? 1 : 0,
                background:
                  'radial-gradient(circle, rgba(250,77,1,0.28) 0%, rgba(250,77,1,0.16) 45%, rgba(250,77,1,0) 72%)',
              }}
            />
            <img
              alt=""
              className="absolute inset-0 block size-full max-w-none transition-opacity duration-200 motion-reduce:transition-none"
              src={option.icon}
              style={{ opacity: active ? 0 : 1 }}
            />
            <img
              alt=""
              className="absolute inset-0 block size-full max-w-none transition-opacity duration-200 motion-reduce:transition-none"
              src={option.iconActive}
              style={{ opacity: active ? 1 : 0 }}
            />
          </button>
        );
      })}
    </div>
  );
}
