import { useState, type FormEvent } from 'react';

/** Adapted from apps/frontend/src/features/waitlist/hooks/useWaitlistForm.ts
 * (#382): same shape, but posts to this project's own /api/waitlist
 * serverless function instead of the real backend's /waitlist route --
 * there is no live backend behind this site. */
export function useWaitlistForm(onSuccess: () => void) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [company, setCompany] = useState(''); // honeypot, never shown
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), name: name.trim() || undefined, company }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.message ?? 'Something went wrong. Please try again.');
      }
      onSuccess();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return { email, setEmail, name, setName, company, setCompany, submitting, error, submit };
}
