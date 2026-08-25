import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useWaitlistForm } from '../hooks/useWaitlistForm';
import { cn } from '@/shared/utils/cn';

interface WaitlistModalProps {
  onClose: () => void;
  /** Landing page's own resolved theme (see LandingPage.tsx) -- this modal
   * has no theme awareness of its own, and the light-mode classes below
   * are left as literal hex rather than switched to tokens, so light-mode
   * output stays pixel-identical to before this prop existed. */
  dark?: boolean;
}

export function WaitlistModal({ onClose, dark = false }: WaitlistModalProps) {
  const [submitted, setSubmitted] = useState(false);
  const { email, setEmail, name, setName, submitting, error, submit } = useWaitlistForm(() => setSubmitted(true));

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
          dark ? 'border-primary/35 bg-card' : 'border-[#fa4d01]/35 bg-[#fffdf9]'
        )}
      >
        {submitted ? (
          <div className="text-center">
            <h2 id="waitlist-modal-title" className={cn('text-xl font-semibold', dark ? 'text-foreground' : 'text-[#30152f]')}>
              You're on the list
            </h2>
            <p className={cn('mt-3 text-sm leading-relaxed', dark ? 'text-muted-foreground' : 'text-[#594555]')}>
              PARTHA is currently in a small, invite-only beta. We'll reach out by email when there's room for you.
            </p>
            <button
              type="button"
              onClick={onClose}
              className={cn(
                'mt-6 w-full rounded-xl px-4 py-2.5 text-sm font-semibold',
                dark
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                  : 'bg-[#fa4d01] text-white hover:bg-[#fa4d01]/90'
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
                  Beta waitlist
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
                  dark
                    ? 'border-primary/30 text-foreground hover:bg-accent'
                    : 'border-[#fa4d01]/30 text-[#30152f] hover:bg-[#fff1e9]'
                )}
              >
                Close
              </button>
            </div>
            <p className={cn('mt-3 text-sm leading-relaxed', dark ? 'text-muted-foreground' : 'text-[#594555]')}>
              PARTHA is invite-only while we work directly with a small group of engineering teams. Leave your email
              and we'll follow up when there's room.
            </p>
            <form onSubmit={submit} className="mt-5 space-y-4">
              <div>
                <label
                  htmlFor="waitlist-email"
                  className={cn('block text-xs font-medium mb-1.5', dark ? 'text-muted-foreground' : 'text-[#594555]')}
                >
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
                    dark ? 'border-input bg-background text-foreground' : 'border-[#fa4d01]/20 bg-white text-[#30152f]'
                  )}
                />
              </div>
              <div>
                <label
                  htmlFor="waitlist-name"
                  className={cn('block text-xs font-medium mb-1.5', dark ? 'text-muted-foreground' : 'text-[#594555]')}
                >
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
                    dark ? 'border-input bg-background text-foreground' : 'border-[#fa4d01]/20 bg-white text-[#30152f]'
                  )}
                />
              </div>

              {error && (
                <p role="alert" className="text-sm text-red-600">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className={cn(
                  'flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-colors disabled:opacity-50',
                  dark
                    ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                    : 'bg-[#fa4d01] text-white hover:bg-[#fa4d01]/90'
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
