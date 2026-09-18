import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useLoginForm } from '@/features/auth/hooks/useLoginForm';
import { OAuthButtons } from '@/features/auth/components/OAuthButtons';
import { AuthShell } from '@/shared/components/layout/AuthShell';
import { PasswordInput } from '@/shared/components/ui/PasswordInput';

export function LoginPage() {
  const { email, setEmail, password, setPassword, submitting, error, submit, redirectState } = useLoginForm();

  return (
    <AuthShell
      title="Hello! Welcome back"
      footer={<>New to Partha?{' '}<Link to="/register" state={redirectState} data-testid="login-register-link" className="text-primary underline underline-offset-2">Create Account</Link></>}
    >
        <OAuthButtons />
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="mb-2 block text-xs text-[#18191b]">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="partha-input h-[46px] w-full px-4 text-sm"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="mb-2 block text-xs text-[#18191b]">
              Password
            </label>
            <PasswordInput
              id="login-password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="partha-input h-[46px] w-full px-4 text-sm"
            />
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
            {submitting ? 'Logging in...' : 'Log In'}
          </button>
        </form>

    </AuthShell>
  );
}
