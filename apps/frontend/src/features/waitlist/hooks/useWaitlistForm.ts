import { useState, type FormEvent } from 'react';
import { getErrorMessage, waitlistService } from '@/shared/services/api';

export function useWaitlistForm(onSuccess: () => void) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await waitlistService.join({ email: email.trim(), name: name.trim() || undefined });
      onSuccess();
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setEmail('');
    setName('');
    setError(null);
  };

  return { email, setEmail, name, setName, submitting, error, submit, reset };
}
