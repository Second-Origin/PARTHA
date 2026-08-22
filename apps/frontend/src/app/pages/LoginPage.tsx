import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useLoginForm } from '@/features/auth/hooks/useLoginForm';
import { AuthShell } from '@/shared/components/layout/AuthShell';

export function LoginPage() {
  const { email, setEmail, password, setPassword, submitting, error, submit, redirectState } = useLoginForm();

  return (
    <AuthShell
      eyebrow="Welcome back"
      title="Sign in to PARTHA"
      description="Continue to your repository intelligence workspace."
      footer={<>Don&apos;t have an account?{' '}<Link to="/register" state={redirectState} data-testid="login-register-link" className="font-medium text-primary underline underline-offset-2">Create one</Link></>}
    >
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-xs font-medium text-muted-foreground mb-1.5">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="partha-input w-full px-3 py-2.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-xs font-medium text-muted-foreground mb-1.5">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="partha-input w-full px-3 py-2.5 text-sm"
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
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_rgba(250,77,1,0.18)] transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

    </AuthShell>
  );
}
