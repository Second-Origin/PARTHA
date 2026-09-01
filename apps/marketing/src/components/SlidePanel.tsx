import { useEffect, useState, type ReactNode } from 'react';

interface SlidePanelProps {
  onClose: () => void;
  labelledBy: string;
  children: ReactNode;
  /** Tailwind max-width class controlling how much of the screen the panel
   * covers on wide viewports. Full-bleed on narrow ones either way. */
  maxWidthClassName?: string;
}

/** Shared slide-in drawer used by every dialog on the reused landing page
 * (DemoModal, RunItYourselfModal, the FAQ panel in App.tsx) -- a centered
 * overlay popup read as an unpolished pattern for a marketing page; a
 * panel that slides in from the side over part of the screen reads as a
 * more deliberate one. Purely presentational: what each dialog shows and
 * does is unchanged, only the container animates and positions
 * differently.
 *
 * Closes on Escape and on a backdrop click, neither of which the previous
 * centered-popup version had -- both are standard drawer behavior and
 * were added here, not carried over from the old pattern. */
export function SlidePanel({ onClose, labelledBy, children, maxWidthClassName = 'max-w-2xl' }: SlidePanelProps) {
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    // Mount closed (off-screen) then flip open on the next frame, so the
    // transform transition actually has something to animate instead of
    // the panel just appearing already in place.
    const frame = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div role="dialog" aria-modal="true" aria-labelledby={labelledBy} className="fixed inset-0 z-50 flex justify-end">
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`absolute inset-0 bg-foreground/30 transition-opacity duration-300 ${entered ? 'opacity-100' : 'opacity-0'}`}
      />
      <div
        className={`relative flex h-full w-full ${maxWidthClassName} flex-col overflow-y-auto border-l border-primary/35 bg-card shadow-2xl transition-transform duration-300 ease-out ${
          entered ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {children}
      </div>
    </div>
  );
}
