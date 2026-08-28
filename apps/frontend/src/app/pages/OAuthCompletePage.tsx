import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuthStore } from '@/app/store/useAuthStore';
import { authService, getErrorMessage } from '@/shared/services/api';
import { AuthShell } from '@/shared/components/layout/AuthShell';

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: 'You cancelled the sign-in request.',
  missing_code: 'The sign-in provider did not return the expected response. Please try again.',
  exchange_failed: "We couldn't verify that sign-in with the provider. Please try again.",
  provider_unavailable: 'This sign-in method is not available right now.',
  account_unavailable: 'This account is not able to sign in right now.',
  already_linked: 'That account is already linked to a different sign-in method.',
  signup_requires_invite:
    "There's no PARTHA account for that yet. PARTHA is invite-only during the beta — create an account with your invite code, then link this provider from Settings.",
};

function messageFor(reason: string | null): string {
  if (reason && ERROR_MESSAGES[reason]) return ERROR_MESSAGES[reason];
  return 'Something went wrong completing sign-in. Please try again.';
}

/** Landing point for every /auth/oauth/{provider}/callback redirect (#288).
 *
 * The backend redirect never carries a body the frontend can read directly
 * -- everything it needs is in this URL's query string, and for a real
 * session it comes back as the httpOnly refresh cookie the callback just
 * set. bootstrap() is exactly the primitive built for that: it already
 * turns "a refresh cookie exists" into a live access token + user, which is
 * the same thing a page reload after any other login does. */
export function OAuthCompletePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setSession = useAuthStore((state) => state.setSession);
  const bootstrap = useAuthStore((state) => state.bootstrap);

  const status = searchParams.get('status');
  const [pendingPassword, setPendingPassword] = useState('');
  const [pendingSubmitting, setPendingSubmitting] = useState(false);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [linkedRedirecting, setLinkedRedirecting] = useState(false);

  useEffect(() => {
    if (status === 'success') {
      bootstrap().then(() => navigate('/dashboard', { replace: true }));
      return;
    }
    if (status === 'linked') {
      setLinkedRedirecting(true);
      bootstrap().then(() => navigate('/settings?tab=General', { replace: true }));
    }
  }, [status, bootstrap, navigate]);

  if (status === 'success' || linkedRedirecting) {
    return <FullPageSpinner label={status === 'linked' ? 'Finishing linking your account…' : 'Finishing sign-in…'} />;
  }

  if (status === 'pending-link') {
    const pendingLinkId = searchParams.get('pendingLinkId');
    const provider = searchParams.get('provider');

    const confirm = async () => {
      if (!pendingLinkId || pendingSubmitting) return;
      setPendingSubmitting(true);
      setPendingError(null);
      try {
        const auth = await authService.confirmOAuthLink({ pendingLinkId, password: pendingPassword });
        setSession(auth);
        navigate('/dashboard', { replace: true });
      } catch (caught) {
        setPendingError(getErrorMessage(caught));
        setPendingSubmitting(false);
      }
    };

    return (
      <AuthShell
        eyebrow="Almost there"
        title="Confirm it's you"
        description={`An account already exists for the email your ${provider ?? 'provider'} account uses. Enter your password to link them.`}
        footer={
          <button type="button" onClick={() => navigate('/login')} className="font-medium text-primary underline underline-offset-2">
            Cancel and go to sign in
          </button>
        }
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            confirm();
          }}
          className="space-y-4"
        >
          <div>
            <label htmlFor="oauth-link-password" className="block text-xs font-medium text-muted-foreground mb-1.5">
              Password
            </label>
            <input
              id="oauth-link-password"
              type="password"
              autoComplete="current-password"
              autoFocus
              required
              value={pendingPassword}
              onChange={(event) => setPendingPassword(event.target.value)}
              className="partha-input w-full px-3 py-2.5 text-sm"
            />
          </div>
          {pendingError && (
            <p role="alert" className="text-sm text-destructive">
              {pendingError}
            </p>
          )}
          <button
            type="submit"
            disabled={pendingSubmitting || !pendingLinkId}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_hsl(var(--primary)/0.18)] transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {pendingSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {pendingSubmitting ? 'Confirming...' : 'Confirm and link account'}
          </button>
        </form>
      </AuthShell>
    );
  }

  // status === 'error' (or anything unrecognized -- same treatment).
  const reason = searchParams.get('reason');
  return (
    <AuthShell
      eyebrow="Sign-in interrupted"
      title="Couldn't complete sign-in"
      description={messageFor(reason)}
      footer={
        <button type="button" onClick={() => navigate('/login')} className="font-medium text-primary underline underline-offset-2">
          Back to sign in
        </button>
      }
    >
      <></>
    </AuthShell>
  );
}

function FullPageSpinner({ label }: { label: string }) {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-primary" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}
