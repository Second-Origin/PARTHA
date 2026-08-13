import { useCallback, useState } from 'react';
import { useAuthStore } from '@/app/store/useAuthStore';
import { authService, getErrorMessage } from '@/shared/services/api';

export function useAccountDeletion() {
  const user = useAuthStore((state) => state.user);
  const accountDeleted = useAuthStore((state) => state.accountDeleted);

  const [expanded, setExpanded] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmEmail, setConfirmEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = useCallback(() => {
    setExpanded(true);
    setError(null);
  }, []);

  const cancel = useCallback(() => {
    setExpanded(false);
    setPassword('');
    setConfirmEmail('');
    setError(null);
  }, []);

  const confirmationMatches = confirmEmail.trim().toLowerCase() === (user?.email ?? '').toLowerCase();
  const canSubmit = confirmationMatches && password.length > 0 && !submitting;

  const deleteAccount = useCallback(async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await authService.deleteAccount({ password, confirmEmail });
      // The backend has already revoked every session and cleared the
      // refresh cookie in its response; there is no signed-in state left to
      // navigate away from -- clearing local state is what makes RequireAuth
      // redirect to /login.
      accountDeleted();
    } catch (caught) {
      setError(getErrorMessage(caught));
      setSubmitting(false);
    }
  }, [accountDeleted, canSubmit, confirmEmail, password]);

  return {
    email: user?.email ?? '',
    expanded,
    open,
    cancel,
    password,
    setPassword,
    confirmEmail,
    setConfirmEmail,
    confirmationMatches,
    canSubmit,
    submitting,
    error,
    deleteAccount,
  };
}
