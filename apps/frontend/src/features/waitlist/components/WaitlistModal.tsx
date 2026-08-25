import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useWaitlistForm } from '../hooks/useWaitlistForm';

interface WaitlistModalProps {
  onClose: () => void;
}

export function WaitlistModal({ onClose }: WaitlistModalProps) {
  const [submitted, setSubmitted] = useState(false);
  const { email, setEmail, name, setName, submitting, error, submit } = useWaitlistForm(() => setSubmitted(true));

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="waitlist-modal-title"
      className="fixed inset-0 z-50 grid place-items-center bg-[#30152f]/30 p-5"
    >
      <div className="w-full max-w-md rounded-3xl border border-[#fa4d01]/35 bg-[#fffdf9] p-6 shadow-2xl sm:p-8">
        {submitted ? (
          <div className="text-center">
            <h2 id="waitlist-modal-title" className="text-xl font-semibold text-[#30152f]">
              You're on the list
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-[#594555]">
              PARTHA is currently in a small, invite-only beta. We'll reach out by email when there's room for you.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-6 w-full rounded-xl bg-[#fa4d01] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#fa4d01]/90"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#fa4d01]">Beta waitlist</p>
                <h2 id="waitlist-modal-title" className="mt-2 text-xl font-semibold text-[#30152f]">
                  Join the waitlist
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-xl border border-[#fa4d01]/30 px-3 py-2 text-sm font-semibold text-[#30152f] hover:bg-[#fff1e9]"
              >
                Close
              </button>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-[#594555]">
              PARTHA is invite-only while we work directly with a small group of engineering teams. Leave your email
              and we'll follow up when there's room.
            </p>
            <form onSubmit={submit} className="mt-5 space-y-4">
              <div>
                <label htmlFor="waitlist-email" className="block text-xs font-medium text-[#594555] mb-1.5">
                  Email
                </label>
                <input
                  id="waitlist-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full rounded-xl border border-[#fa4d01]/20 bg-white px-3 py-2.5 text-sm text-[#30152f]"
                />
              </div>
              <div>
                <label htmlFor="waitlist-name" className="block text-xs font-medium text-[#594555] mb-1.5">
                  Name <span className="font-normal">(optional)</span>
                </label>
                <input
                  id="waitlist-name"
                  type="text"
                  autoComplete="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="w-full rounded-xl border border-[#fa4d01]/20 bg-white px-3 py-2.5 text-sm text-[#30152f]"
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
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#fa4d01] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#fa4d01]/90 disabled:opacity-50"
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
