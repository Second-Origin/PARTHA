import { Link } from 'react-router-dom';
import { Hexagon, Loader2 } from 'lucide-react';
import { useLoginForm } from '@/features/auth/hooks/useLoginForm';

export function LoginPage() {
  const { email, setEmail, password, setPassword, submitting, error, submit, redirectState } = useLoginForm();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Hexagon className="h-5 w-5" />
          </div>
          <h1 className="text-lg font-semibold text-foreground">Sign in to PARTHA</h1>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-xl border border-border bg-card p-6">
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
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
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
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
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
            className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{' '}
          <Link to="/register" state={redirectState} className="text-primary hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
