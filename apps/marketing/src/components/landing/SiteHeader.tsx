import { useEffect, useState } from 'react';

import imgMark from '@/assets/landing/figma/vector52.png';
import imgWordmark from '@/assets/landing/figma/vector50.svg';
import imgWordmarkDark from '@/assets/landing/wordmark-vector50-dark.svg';

const REPO_URL = 'https://github.com/Second-Origin/PARTHA';

const NAV = [
  { label: 'Product', href: '#product' },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Capabilities', href: '#capabilities' },
  { label: 'FAQ', href: '#faq' },
] as const;

/** The site header, as a real responsive bar rather than part of the canvas.
 *
 * The page body is the design's fixed 1728px composition scaled to the
 * viewport, which is right for the artwork but wrong for the header: at phone
 * widths it scaled down to a few unreadable, untappable pixels. So the header
 * is lifted out and built at its natural size, and `LandingScaler` crops the
 * band it used to occupy off the top of the canvas.
 *
 * It keeps the design's vocabulary -- the bar tint, the wordmark, Montserrat
 * nav, the orange pill -- while behaving like a header: sticky, full-size
 * targets, and a disclosure menu once the links no longer fit.
 */
export function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false);

  // A menu left open across a resize would be stranded once the inline links
  // come back, so it closes when the layout changes under it.
  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    window.addEventListener('resize', close);
    return () => window.removeEventListener('resize', close);
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  const navLink =
    'font-display text-[15px] font-medium capitalize text-[var(--ln-ink)] transition-opacity hover:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#fa4d01]';

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[rgba(250,77,1,0.15)] bg-[var(--ln-bar)]">
      <div className="mx-auto flex h-[64px] w-full max-w-[1728px] items-center justify-between gap-4 px-4 sm:h-[72px] sm:px-6 lg:px-[78px]">
        <a
          href="#top"
          aria-label="PARTHA, back to top"
          onClick={(event) => {
            event.preventDefault();
            setMenuOpen(false);
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          className="flex shrink-0 items-center gap-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#fa4d01]"
        >
          <img alt="" src={imgMark} className="h-[26px] w-[26px] sm:h-[30px] sm:w-[30px]" />
          <img alt="PARTHA" src={imgWordmark} className="wordmark-light h-[16px] sm:h-[19px]" />
          <img alt="PARTHA" src={imgWordmarkDark} className="wordmark-dark h-[16px] sm:h-[19px]" />
        </a>

        <nav aria-label="Primary" className="hidden items-center gap-7 lg:flex">
          {NAV.map((item) => (
            <a key={item.label} href={item.href} className={navLink}>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="rounded-[25px] border-2 border-[#fa4d01] bg-[#fffcf7] px-3 py-[7px] font-display text-[13px] font-medium text-[#fa4d01] transition-colors hover:bg-[#fa4d01] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01] sm:px-4 sm:text-[15px]"
          >
            Try PARTHA v0.2.0
          </a>

          <button
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            aria-controls="site-menu"
            onClick={() => setMenuOpen((open) => !open)}
            className="grid size-[38px] place-items-center rounded-xl border border-[rgba(250,77,1,0.3)] text-[var(--ln-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#fa4d01] lg:hidden"
          >
            <span aria-hidden className="relative block h-[12px] w-[18px]">
              <span
                className={`absolute left-0 block h-[2px] w-full bg-current transition-transform duration-200 ${
                  menuOpen ? 'top-[5px] rotate-45' : 'top-0'
                }`}
              />
              <span
                className={`absolute left-0 top-[5px] block h-[2px] w-full bg-current transition-opacity duration-200 ${
                  menuOpen ? 'opacity-0' : 'opacity-100'
                }`}
              />
              <span
                className={`absolute left-0 block h-[2px] w-full bg-current transition-transform duration-200 ${
                  menuOpen ? 'top-[5px] -rotate-45' : 'top-[10px]'
                }`}
              />
            </span>
          </button>
        </div>
      </div>

      <nav
        id="site-menu"
        aria-label="Primary"
        hidden={!menuOpen}
        className="border-t border-[rgba(250,77,1,0.15)] bg-[var(--ln-bar)] px-4 pb-4 pt-2 sm:px-6 lg:hidden"
      >
        <ul className="flex flex-col">
          {NAV.map((item) => (
            <li key={item.label}>
              <a
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className={`${navLink} block py-3 text-[17px]`}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
