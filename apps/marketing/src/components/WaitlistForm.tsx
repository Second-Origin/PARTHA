import { useState, type FormEvent } from 'react';

interface WaitlistFormProps {
  onClose: () => void;
}

type Status = 'idle' | 'submitting' | 'done';

export function WaitlistForm({ onClose }: WaitlistFormProps) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  // Honeypot: never rendered visibly, never touched by a real visitor.
  const [company, setCompany] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (status === 'submitting') return;
    setStatus('submitting');
    setError(null);
    try {
      const response = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name, company }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.message ?? 'Something went wrong. Please try again.');
      }
      setStatus('done');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Something went wrong. Please try again.');
      setStatus('idle');
    }
  };

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="waitlist-title" className="fixed inset-0 z-50 grid place-items-center bg-foreground/30 p-5">
      <div className="w-full max-w-md rounded-3xl border border-primary/25 bg-card p-6 shadow-2xl sm:p-8">
        {status === 'done' ? (
          <div className="text-center">
            <h2 id="waitlist-title" className="text-xl font-semibold text-foreground">
              You&apos;re on the list
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              We&apos;ll reach out by email when there&apos;s room. In the meantime, the real product is open source —
              you can run it yourself right now.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-6 w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">Waitlist</p>
                <h2 id="waitlist-title" className="mt-2 text-xl font-semibold text-foreground">
                  Join the waitlist
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-xl border border-border px-3 py-2 text-sm font-semibold text-foreground hover:bg-accent"
              >
                Close
              </button>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              PARTHA isn&apos;t running as a hosted service right now. Leave your email and we&apos;ll follow up when
              a hosted beta is ready — or run it yourself in the meantime.
            </p>
            <form onSubmit={submit} className="mt-5 space-y-4">
              <div>
                <label htmlFor="waitlist-email" className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Email
                </label>
                <input
                  id="waitlist-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground"
                />
              </div>
              <div>
                <label htmlFor="waitlist-name" className="mb-1.5 block text-xs font-medium text-muted-foreground">
                  Name <span className="font-normal">(optional)</span>
                </label>
                <input
                  id="waitlist-name"
                  type="text"
                  autoComplete="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="w-full rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground"
                />
              </div>
              {/* Honeypot -- visually hidden and unreachable by tab order, so a
                  real visitor never sees or fills it. */}
              <div aria-hidden="true" className="absolute left-[-9999px] top-auto h-0 w-0 overflow-hidden">
                <label htmlFor="waitlist-company">Company</label>
                <input
                  id="waitlist-company"
                  type="text"
                  tabIndex={-1}
                  autoComplete="off"
                  value={company}
                  onChange={(event) => setCompany(event.target.value)}
                />
              </div>

              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={status === 'submitting'}
                className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {status === 'submitting' ? 'Submitting…' : 'Join the waitlist'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
