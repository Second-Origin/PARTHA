import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/app/store/useAuthStore';
import { getErrorMessage } from '@/shared/services/api';
import { resolveRedirectTarget } from '../authRedirect';

export function useLoginForm() {
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate(resolveRedirectTarget(location.state), { replace: true });
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  // Forwarded to the "create one"/"sign in" link so bouncing between login
  // and register never loses the originally-intended destination.
  return { email, setEmail, password, setPassword, submitting, error, submit, redirectState: location.state };
}
