import parthaLogo from '@/assets/partha-logo.svg';
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { FOOTER_COPYRIGHT, FOOTER_TAGLINE } from '@/data/landing';
import { FOOTER_COLUMNS } from '@/data/site';
import type { LandingThemePreference } from '@/hooks/useLandingTheme';

type Props = {
  themePreference: LandingThemePreference;
  onThemeChange: (preference: LandingThemePreference) => void;
};

/** Footer: brand block, four link columns, copyright, and the theme control. */
export function SiteFooter({ themePreference, onThemeChange }: Props) {
  return (
    <footer className="bg-[var(--ln-bar)]">
      <div className="mx-auto w-full max-w-[1568px] px-6 pb-8 pt-[62px] lg:px-10 lg:pt-[86px]">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)] lg:gap-16">
          <div>
            <img src={parthaLogo} alt="PARTHA" className="h-[44px] w-auto lg:h-[52px]" />
            <p className="mt-4 max-w-[46ch] font-accent text-[14px] leading-[1.45] text-[var(--ln-ink-muted)] lg:text-[15px]">
              {FOOTER_TAGLINE}
            </p>
          </div>

          <nav aria-label="Footer" className="grid grid-cols-2 gap-8 sm:grid-cols-4 lg:gap-10">
            {FOOTER_COLUMNS.map((column) => (
              <div key={column.heading}>
                <h2 className="font-display text-[13px] font-medium uppercase tracking-[0.08em] text-[var(--ln-ink-muted)] lg:text-[15px]">
                  {column.heading}
                </h2>
                <ul className="mt-4 space-y-[13px]">
                  {column.links.map((link) => (
                    <li key={`${column.heading}-${link.label}`}>
                      <a
                        href={link.href}
                        {...(link.external ? { target: '_blank', rel: 'noreferrer' } : {})}
                        className="rounded font-display text-[16px] font-light text-[var(--ln-ink)] transition-colors hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary lg:text-[19px]"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>

        <div className="mt-[46px] flex flex-col-reverse items-center gap-5 border-t border-primary/20 pt-6 sm:flex-row sm:justify-between">
          <p className="font-accent text-[14px] text-[var(--ln-ink-soft)] lg:text-[15px]">{FOOTER_COPYRIGHT}</p>
          <ThemeSwitcher preference={themePreference} onChange={onThemeChange} />
        </div>
      </div>
    </footer>
  );
}
