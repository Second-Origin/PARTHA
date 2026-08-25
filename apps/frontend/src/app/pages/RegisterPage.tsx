import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { PASSWORD_MIN_LENGTH, useRegisterForm } from '@/features/auth/hooks/useRegisterForm';
import { AuthShell } from '@/shared/components/layout/AuthShell';

export function RegisterPage() {
  const {
    email,
    setEmail,
    password,
    setPassword,
    inviteCode,
    setInviteCode,
    submitting,
    error,
    submit,
    redirectState,
  } = useRegisterForm();

  return (
    <AuthShell
      eyebrow="Start exploring"
      title="Create your PARTHA account"
      description="Build a private, evidence-backed view of your codebase."
      footer={<>Already have an account?{' '}<Link to="/login" state={redirectState} className="font-medium text-primary underline underline-offset-2">Sign in</Link></>}
    >
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="register-email" className="block text-xs font-medium text-muted-foreground mb-1.5">
              Email
            </label>
            <input
              id="register-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="partha-input w-full px-3 py-2.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="register-password" className="block text-xs font-medium text-muted-foreground mb-1.5">
              Password
            </label>
            <input
              id="register-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={PASSWORD_MIN_LENGTH}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="partha-input w-full px-3 py-2.5 text-sm"
            />
            <p className="mt-1.5 text-2xs text-muted-foreground">At least {PASSWORD_MIN_LENGTH} characters.</p>
          </div>
          <div>
            <label htmlFor="register-invite-code" className="block text-xs font-medium text-muted-foreground mb-1.5">
              Invite code
            </label>
            <input
              id="register-invite-code"
              type="text"
              autoComplete="off"
              required
              value={inviteCode}
              onChange={(event) => setInviteCode(event.target.value)}
              className="partha-input w-full px-3 py-2.5 text-sm"
            />
            <p className="mt-1.5 text-2xs text-muted-foreground">
              PARTHA is invite-only during the beta. No code?{' '}
              <a
                href="https://discord.gg/qvk9DcxDA"
                target="_blank"
                rel="noreferrer"
                className="text-primary underline underline-offset-2"
              >
                Get in touch
              </a>
              .
            </p>
          </div>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_hsl(var(--primary)/0.18)] transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? 'Creating account...' : 'Create account'}
          </button>
        </form>

    </AuthShell>
  );
}
