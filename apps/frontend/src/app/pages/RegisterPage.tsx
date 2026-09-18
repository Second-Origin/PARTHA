import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { PASSWORD_MIN_LENGTH, useRegisterForm } from '@/features/auth/hooks/useRegisterForm';
import { AuthShell } from '@/shared/components/layout/AuthShell';
import { PasswordInput } from '@/shared/components/ui/PasswordInput';

export function RegisterPage() {
  const { email, setEmail, password, setPassword, submitting, error, submit, redirectState } = useRegisterForm();

  return (
    <AuthShell
      title="Create a Partha account"
      footer={<>Already have an account?{' '}<Link to="/login" state={redirectState} className="text-primary underline underline-offset-2">Log in</Link></>}
    >
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="register-email" className="mb-2 block text-xs text-[#18191b]">
              Email
            </label>
            <input
              id="register-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="partha-input h-[46px] w-full px-4 text-sm"
            />
            {/* #374: registration is now gated by an admin-approved email
                allowlist, not an invite code -- an unapproved email surfaces
                as the `error` alert below once submitted, but this stays
                visible up front so it isn't a surprise. */}
            <p className="mt-1.5 text-2xs text-muted-foreground">
              The first account on a new install becomes its owner. After that, each new email must be approved
              by whoever runs this install.
            </p>
          </div>
          <div>
            <label htmlFor="register-password" className="mb-2 block text-xs text-[#18191b]">
              Password
            </label>
            <PasswordInput
              id="register-password"
              autoComplete="new-password"
              required
              minLength={PASSWORD_MIN_LENGTH}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="partha-input h-[46px] w-full px-4 text-sm"
            />
            <p className="mt-1.5 text-2xs text-muted-foreground">At least {PASSWORD_MIN_LENGTH} characters.</p>
          </div>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex h-8 w-full items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

    </AuthShell>
  );
}
