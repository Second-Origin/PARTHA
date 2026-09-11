import { useEffect, useRef, useState } from 'react';

import imgMark from '@/assets/landing/figma/vector52.png';
import imgWordmark from '@/assets/landing/figma/vector50.svg';
import imgWordmarkDark from '@/assets/landing/wordmark-vector50-dark.svg';
import { CANVAS_WIDTH } from '@/components/landing/LandingScaler';

const REPO_URL = 'https://github.com/Second-Origin/PARTHA';

/** The header band's own height inside the design canvas. */
export const HEADER_HEIGHT = 133;

/* The design's own header geometry, in canvas units. Every number here is
 * lifted from the canvas markup it replaces, so at full width this renders
 * pixel-for-pixel what the design draws. */
const NAV = [
  { label: 'Product', href: '#product', centre: 541.5, width: 103 },
  { label: 'How it works', href: '#how-it-works', centre: 727.5, width: 177 },
  { label: 'Capabilities', href: '#capabilities', centre: 931, width: 152 },
  { label: 'FAQ', href: '#faq', centre: 1073, width: 54 },
] as const;

const BAR = { left: 463, top: 40, width: 669, height: 52 };
const LOGO = { left: 78, top: 40, width: 205, height: 53 };
const CTA = { left: 1418, top: 41, width: 232, height: 52 };

/** Below this viewport width the design's row no longer fits legibly, and the
 * header switches to a layout built for the space instead of a shrunk copy. */
const COMPACT_BELOW = 1024;

/** The site header.
 *
 * The page body is the design's fixed 1728px composition scaled to the
 * viewport. The header used to be part of that, which meant at phone widths it
 * scaled down with everything else into a few unreadable, untappable pixels.
 *
 * So it is lifted out, but it is *not* re-proportioned: at desktop widths this
 * renders the design's own geometry -- the 205x53 mark, the 669x52 nav bar, its
 * 24px Montserrat links, the 232x52 pill -- scaled by exactly the factor the
 * canvas beneath it uses, so the two stay locked together and the header looks
 * as drawn. Only once the row genuinely cannot fit does it become a compact bar
 * with a disclosure menu, at sizes chosen for that space rather than shrunk.
 */
export function SiteHeader() {
  const hostRef = useRef<HTMLElement>(null);
  const [scale, setScale] = useState(1);
  const [compact, setCompact] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const measure = () => {
      const available = host.clientWidth;
      if (available <= 0) return;
      setScale(available / CANVAS_WIDTH);
      const isCompact = available < COMPACT_BELOW;
      setCompact(isCompact);
      // A menu left open as the row comes back would be stranded behind it.
      if (!isCompact) setMenuOpen(false);
    };

    measure();
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    observer?.observe(host);
    window.addEventListener('resize', measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  const backToTop = (event: { preventDefault: () => void }) => {
    event.preventDefault();
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const focusRing =
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#fa4d01]';

  return (
    <header
      ref={hostRef}
      className="sticky top-0 z-40 w-full overflow-hidden bg-[var(--ln-bar)]"
      style={{ height: compact ? undefined : HEADER_HEIGHT * scale }}
    >
      {compact ? (
        <>
          <div className="flex h-[64px] items-center justify-between gap-3 px-4 sm:px-6">
            <a href="#top" aria-label="PARTHA, back to top" onClick={backToTop} className={`flex shrink-0 items-center gap-2 ${focusRing}`}>
              <img alt="" src={imgMark} className="h-[28px] w-[28px]" />
              <img alt="PARTHA" src={imgWordmark} className="wordmark-light h-[17px]" />
              <img alt="PARTHA" src={imgWordmarkDark} className="wordmark-dark h-[17px]" />
            </a>

            <div className="flex items-center gap-2">
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer"
                className={`rounded-[25px] border-2 border-[#fa4d01] bg-[#fffcf7] px-3 py-[6px] font-display text-[13px] font-medium text-[#fa4d01] transition-colors hover:bg-[#fa4d01] hover:text-white ${focusRing}`}
              >
                Try PARTHA v0.2.0
              </a>
              <button
                type="button"
                aria-label={menuOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={menuOpen}
                aria-controls="site-menu"
                onClick={() => setMenuOpen((open) => !open)}
                className={`grid size-[38px] place-items-center rounded-xl border border-[rgba(250,77,1,0.3)] text-[var(--ln-ink)] ${focusRing}`}
              >
                <span aria-hidden className="relative block h-[12px] w-[18px]">
                  <span className={`absolute left-0 block h-[2px] w-full bg-current transition-transform duration-200 ${menuOpen ? 'top-[5px] rotate-45' : 'top-0'}`} />
                  <span className={`absolute left-0 top-[5px] block h-[2px] w-full bg-current transition-opacity duration-200 ${menuOpen ? 'opacity-0' : 'opacity-100'}`} />
                  <span className={`absolute left-0 block h-[2px] w-full bg-current transition-transform duration-200 ${menuOpen ? 'top-[5px] -rotate-45' : 'top-[10px]'}`} />
                </span>
              </button>
            </div>
          </div>

          <nav id="site-menu" aria-label="Primary" hidden={!menuOpen} className="border-t border-[rgba(250,77,1,0.15)] px-4 pb-4 pt-1 sm:px-6">
            <ul className="flex flex-col">
              {NAV.map((item) => (
                <li key={item.label}>
                  <a
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className={`block py-3 font-display text-[17px] font-medium capitalize text-[var(--ln-ink)] ${focusRing}`}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </>
      ) : (
        /* The design's own row, at the canvas's scale. */
        <div
          style={{
            width: CANVAS_WIDTH,
            height: HEADER_HEIGHT,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
          }}
          className="relative"
        >
          <a
            href="#top"
            aria-label="PARTHA, back to top"
            onClick={backToTop}
            className={`absolute block overflow-clip ${focusRing}`}
            style={{ left: LOGO.left, top: LOGO.top, width: LOGO.width, height: LOGO.height }}
          >
            <img alt="" src={imgMark} className="absolute left-0 top-[3px] h-[44px] w-[44px]" />
            <img alt="PARTHA" src={imgWordmark} className="wordmark-light absolute left-[56px] top-[15px] h-[26px]" />
            <img alt="PARTHA" src={imgWordmarkDark} className="wordmark-dark absolute left-[56px] top-[15px] h-[26px]" />
          </a>

          <div
            className="absolute rounded-[26px]"
            style={{ left: BAR.left, top: BAR.top, width: BAR.width, height: BAR.height }}
          />

          <nav aria-label="Primary">
            {NAV.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className={`absolute block -translate-x-1/2 whitespace-nowrap text-center font-display text-[24px] font-medium capitalize leading-none text-[var(--ln-ink)] transition-opacity hover:opacity-70 ${focusRing}`}
                style={{ left: item.centre, top: 51.99, width: item.width }}
              >
                {item.label}
              </a>
            ))}
          </nav>

          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className={`group absolute block ${focusRing}`}
            style={{ left: CTA.left, top: CTA.top, width: CTA.width, height: CTA.height }}
          >
            <span className="absolute inset-0 rounded-[25px] border-[3px] border-solid border-[#fa4d01] bg-[#fffcf7] transition-colors duration-200 group-hover:bg-[#fa4d01]" />
            <span className="absolute inset-0 grid place-items-center font-display text-[24px] font-medium text-[#fa4d01] transition-colors duration-200 group-hover:text-white">
              Try PARTHA v0.2.0
            </span>
          </a>
        </div>
      )}
    </header>
  );
}
