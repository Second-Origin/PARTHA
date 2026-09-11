import { useEffect, useRef, useState, type ReactNode } from 'react';

/** The design's native canvas size (Figma frame "Landing Page" 1:2). */
export const CANVAS_WIDTH = 1728;
export const CANVAS_HEIGHT = 5608;

type Props = {
  children: ReactNode;
  /** Pixels to clip off the top of the canvas, in canvas units.
   *
   * The design draws the header into the composition. A real header is built
   * separately so it can behave at any width, so the band the canvas spends on
   * its own header is cropped away here rather than showing through behind it. */
  cropTop?: number;
};

/** Renders the design canvas at its authored 1728px width and scales it to fit
 * the viewport.
 *
 * The design is a fixed composition: every box in it is absolutely positioned
 * against a 1728x5608 frame. Reflowing it into a fluid layout changes the
 * geometry, so instead the whole canvas is scaled uniformly. Proportions,
 * spacing, and every layer relationship stay exactly as authored, and unlike
 * the flat SVG this replaced, the content underneath is real DOM: selectable
 * text, focusable controls, working hover states.
 *
 * The outer element reserves the scaled height so the page scrolls correctly,
 * and the scale factor is recomputed on resize. */
export function LandingScaler({ children, cropTop = 0 }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const measure = () => {
      const available = host.clientWidth;
      if (available > 0) setScale(available / CANVAS_WIDTH);
    };

    measure();

    // ResizeObserver catches the host changing width for reasons a resize
    // event does not report -- a sidebar opening, a zoom change. Where it is
    // not available the resize listener alone still keeps the scale correct.
    const observer =
      typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    observer?.observe(host);
    window.addEventListener('resize', measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, []);

  return (
    <div
      ref={hostRef}
      className="w-full overflow-hidden"
      style={{ height: (CANVAS_HEIGHT - cropTop) * scale }}
    >
      <div
        style={{
          width: CANVAS_WIDTH,
          height: CANVAS_HEIGHT,
          transform: `scale(${scale}) translateY(${-cropTop}px)`,
          transformOrigin: 'top left',
        }}
      >
        {children}
      </div>
    </div>
  );
}
