import { useEffect, useRef, useState, type ReactNode } from 'react';

interface SlidePanelProps {
  onClose: () => void;
  labelledBy: string;
  /** Shown in the panel's own bar, next to the close control. */
  eyebrow: string;
  children: ReactNode;
}

/** A full-screen panel that slides down over the page.
 *
 * The landing page is one tall composition; sending someone to a separate
 * route to read a walkthrough loses their place in it. This covers the page
 * instead and leaves it underneath, so closing returns them exactly where
 * they were.
 *
 * Behaviour: closes on Escape, on the close control and on a click in the
 * strip of page still visible beneath it; locks background scroll while open;
 * and moves focus into the panel on mount so keyboard and screen-reader users
 * start inside it rather than behind it.
 */
export function SlidePanel({ onClose, labelledBy, eyebrow, children }: SlidePanelProps) {
  const [entered, setEntered] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Mount above the viewport, then drop into place on the next frame so the
    // transition has something to animate rather than appearing already open.
    const frame = requestAnimationFrame(() => setEntered(true));
    panelRef.current?.focus();
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div role="dialog" aria-modal="true" aria-labelledby={labelledBy} className="fixed inset-0 z-50">
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`absolute inset-0 bg-foreground/40 backdrop-blur-[2px] transition-opacity duration-300 ${
          entered ? 'opacity-100' : 'opacity-0'
        }`}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`absolute inset-x-0 top-0 flex h-[92vh] flex-col overflow-hidden rounded-b-3xl border-b border-primary/20 bg-card shadow-2xl outline-none transition-transform duration-[420ms] ease-out motion-reduce:transition-none ${
          entered ? 'translate-y-0' : '-translate-y-full'
        }`}
      >
        <div className="flex shrink-0 items-center justify-between gap-4 border-b border-primary/15 px-5 py-4 sm:px-8">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">{eyebrow}</p>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-primary/30 px-3 py-2 text-sm font-semibold text-foreground transition-colors hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
