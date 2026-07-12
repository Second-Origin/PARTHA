import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/app/store/useAuthStore';
import { getErrorMessage } from '@/shared/services/api';
import { resolveRedirectTarget } from '../authRedirect';

// Mirrors PASSWORD_MIN_LENGTH in apps/backend/app/schemas/auth.py — checked
// client-side too so a too-short password fails instantly, not after a
// round trip to the backend.
export const PASSWORD_MIN_LENGTH = 10;

export function useRegisterForm() {
  const register = useAuthStore((state) => state.register);
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    if (password.length < PASSWORD_MIN_LENGTH) {
      setError(`Password must be at least ${PASSWORD_MIN_LENGTH} characters.`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await register(email.trim(), password);
      navigate(resolveRedirectTarget(location.state), { replace: true });
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  // Forwarded to the "sign in" link so bouncing between register and login
  // never loses the originally-intended destination.
  return { email, setEmail, password, setPassword, submitting, error, submit, redirectState: location.state };
}
