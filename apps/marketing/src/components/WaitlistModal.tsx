import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useWaitlistForm } from '@/hooks/useWaitlistForm';
import { cn } from '@/utils/cn';

interface WaitlistModalProps {
  onClose: () => void;
  dark?: boolean;
}

/** Ported from apps/frontend/src/features/waitlist/components/WaitlistModal.tsx
 * (#382) -- same visual design (including its light-mode literal hex
 * colors, kept pixel-identical rather than switched to tokens, exactly as
 * the original component's own comment explains), adapted with a honeypot
 * field and pointed at this project's own /api/waitlist instead of the
 * real backend. */
export function WaitlistModal({ onClose, dark = false }: WaitlistModalProps) {
  const [submitted, setSubmitted] = useState(false);
  const { email, setEmail, name, setName, company, setCompany, submitting, error, submit } = useWaitlistForm(() =>
    setSubmitted(true),
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="waitlist-modal-title"
      className={cn('fixed inset-0 z-50 grid place-items-center p-5', dark ? 'bg-foreground/30' : 'bg-[#30152f]/30')}
    >
      <div
        className={cn(
          'w-full max-w-md rounded-3xl border p-6 shadow-2xl sm:p-8',
          dark ? 'border-primary/35 bg-card' : 'border-[#fa4d01]/35 bg-[#fffdf9]',
        )}
      >
        {submitted ? (
          <div className="text-center">
            <h2 id="waitlist-modal-title" className={cn('text-xl font-semibold', dark ? 'text-foreground' : 'text-[#30152f]')}>
              You&apos;re on the list
            </h2>
            <p className={cn('mt-3 text-sm leading-relaxed', dark ? 'text-muted-foreground' : 'text-[#594555]')}>
              PARTHA isn&apos;t running as a hosted service right now. We&apos;ll reach out by email when a hosted
              beta is ready.
            </p>
            <button
              type="button"
              onClick={onClose}
              className={cn(
                'mt-6 w-full rounded-xl px-4 py-2.5 text-sm font-semibold',
                dark ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-[#fa4d01] text-white hover:bg-[#fa4d01]/90',
              )}
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className={cn('text-xs font-semibold uppercase tracking-[0.14em]', dark ? 'text-primary' : 'text-[#fa4d01]')}>
                  Waitlist
                </p>
                <h2 id="waitlist-modal-title" className={cn('mt-2 text-xl font-semibold', dark ? 'text-foreground' : 'text-[#30152f]')}>
                  Join the waitlist
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className={cn(
                  'rounded-xl border px-3 py-2 text-sm font-semibold',
                  dark ? 'border-primary/30 text-foreground hover:bg-accent' : 'border-[#fa4d01]/30 text-[#30152f] hover:bg-[#fff1e9]',
                )}
              >
                Close
              </button>
            </div>
            <p className={cn('mt-3 text-sm leading-relaxed', dark ? 'text-muted-foreground' : 'text-[#594555]')}>
              PARTHA isn&apos;t running as a hosted service right now. Leave your email and we&apos;ll follow up when
              a hosted beta is ready -- or run it yourself in the meantime.
            </p>
            <form onSubmit={submit} className="mt-5 space-y-4">
              <div>
                <label htmlFor="waitlist-email" className={cn('mb-1.5 block text-xs font-medium', dark ? 'text-muted-foreground' : 'text-[#594555]')}>
                  Email
                </label>
                <input
                  id="waitlist-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className={cn(
                    'w-full rounded-xl border px-3 py-2.5 text-sm',
                    dark ? 'border-input bg-background text-foreground' : 'border-[#fa4d01]/20 bg-white text-[#30152f]',
                  )}
                />
              </div>
              <div>
                <label htmlFor="waitlist-name" className={cn('mb-1.5 block text-xs font-medium', dark ? 'text-muted-foreground' : 'text-[#594555]')}>
                  Name <span className="font-normal">(optional)</span>
                </label>
                <input
                  id="waitlist-name"
                  type="text"
                  autoComplete="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className={cn(
                    'w-full rounded-xl border px-3 py-2.5 text-sm',
                    dark ? 'border-input bg-background text-foreground' : 'border-[#fa4d01]/20 bg-white text-[#30152f]',
                  )}
                />
              </div>
              {/* Honeypot -- visually hidden, unreachable by tab order. */}
              <div aria-hidden="true" className="absolute left-[-9999px] top-auto h-0 w-0 overflow-hidden">
                <label htmlFor="waitlist-company">Company</label>
                <input id="waitlist-company" type="text" tabIndex={-1} autoComplete="off" value={company} onChange={(event) => setCompany(event.target.value)} />
              </div>

              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className={cn(
                  'flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-colors disabled:opacity-50',
                  dark ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-[#fa4d01] text-white hover:bg-[#fa4d01]/90',
                )}
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {submitting ? 'Submitting...' : 'Join the waitlist'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
