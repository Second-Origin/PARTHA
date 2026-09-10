import { useEffect, useState } from 'react';

import parthaLogo from '@/assets/partha-logo.svg';
import { NAV_LINKS } from '@/data/landing';
import { cn } from '@/utils/cn';

type Props = {
  /** Opens the scripted product walkthrough (this site has no real login). */
  onLogIn: () => void;
  /** Opens the run-it-yourself setup instructions. */
  onCreateAccount: () => void;
};

/** Sticky top bar: brand, section nav, and the two account actions.
 *
 * The design places this on the cream surface at the top of the page; once the
 * hero scrolls under it we add a hairline and a blur so the nav stays legible
 * over the story cards. */
export function SiteHeader({ onLogIn, onCreateAccount }: Props) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={cn(
        'sticky top-0 z-50 w-full bg-[var(--ln-bar)] transition-shadow duration-200',
        scrolled && 'shadow-[0_1px_0_0_rgba(57,33,53,0.08)] backdrop-blur-sm',
      )}
    >
      <div className="mx-auto flex h-[76px] w-full max-w-[1568px] items-center justify-between gap-3 px-4 sm:h-[92px] sm:gap-6 sm:px-6 lg:h-[133px] lg:px-10">
        <a href="#top" className="shrink-0 rounded-md focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary" aria-label="PARTHA home">
          <img src={parthaLogo} alt="PARTHA" className="h-[26px] w-auto sm:h-[34px] lg:h-[42px]" />
        </a>

        <nav aria-label="Landing page sections" className="hidden lg:block">
          <ul className="flex items-center gap-[52px]">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  className="rounded-md font-display text-[18px] font-medium text-[var(--ln-hero-head)] transition-colors hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex shrink-0 items-center gap-3 sm:gap-4 lg:gap-[26px]">
          {/* Below 400px the two actions plus the wordmark do not fit; Log In
              opens the same walkthrough as the hero's secondary action, so it
              is the one that folds away. */}
          <button
            type="button"
            onClick={onLogIn}
            className="hidden rounded-md font-display text-[15px] font-medium text-[var(--ln-hero-head)] transition-colors hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary min-[400px]:block sm:text-[16px] lg:text-[18px]"
          >
            Log In
          </button>
          <button
            type="button"
            onClick={onCreateAccount}
            className="whitespace-nowrap rounded-full border-[1.5px] border-primary px-3 py-2 font-display text-[13px] font-semibold text-primary transition-colors hover:bg-primary hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:px-4 sm:py-[9px] sm:text-[15px] lg:px-[26px] lg:py-[11px] lg:text-[17px]"
          >
            Create account
          </button>
        </div>
      </div>
    </header>
  );
}
