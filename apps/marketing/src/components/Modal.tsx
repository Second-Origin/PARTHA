import { useEffect, useRef, useState, type ReactNode } from 'react';

interface ModalProps {
  onClose: () => void;
  labelledBy: string;
  children: ReactNode;
  /** Tailwind max-width class controlling how wide the dialog is on larger
   * viewports. Full-width (minus page gutters) on narrow ones either way. */
  maxWidthClassName?: string;
}

/** Shared centered modal dialog used by every overlay on the reused landing
 * page (DemoModal, RunItYourselfModal, the FAQ panel in App.tsx).
 *
 * A centered card over a dimmed backdrop is the conventional pattern for a
 * marketing page's supporting dialogs -- it reads as part of the page rather
 * than as an app chrome element sliding in from the edge. Purely
 * presentational: what each dialog shows and does is unchanged, only the
 * container positions and animates.
 *
 * Behavior: closes on Escape and on a backdrop click, locks background
 * scroll while open, and moves focus to the dialog on mount so keyboard and
 * screen-reader users start inside it. */
export function Modal({ onClose, labelledBy, children, maxWidthClassName = 'max-w-2xl' }: ModalProps) {
  const [entered, setEntered] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Mount hidden (slightly down and scaled back) then flip to the resting
    // state on the next frame, so the transition has something to animate
    // instead of the card just appearing already in place.
    const frame = requestAnimationFrame(() => setEntered(true));
    panelRef.current?.focus();
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
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
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelledBy}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
    >
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`absolute inset-0 bg-foreground/40 backdrop-blur-[2px] transition-opacity duration-200 ${
          entered ? 'opacity-100' : 'opacity-0'
        }`}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`relative flex max-h-[calc(100vh-2rem)] w-full ${maxWidthClassName} flex-col overflow-y-auto rounded-2xl border border-primary/20 bg-card shadow-2xl outline-none transition-all duration-200 ease-out ${
          entered ? 'translate-y-0 scale-100 opacity-100' : 'translate-y-2 scale-[0.98] opacity-0'
        }`}
      >
        {children}
      </div>
    </div>
  );
}
