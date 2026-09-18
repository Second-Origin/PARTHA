import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { BrandLogo } from '@/shared/components/ui/BrandLogo';

interface AuthShellProps {
  title: string;
  /** Only for states that need explaining (e.g. an OAuth error); the plain
   * sign-in and sign-up forms carry none, as in the design. */
  description?: string;
  children: ReactNode;
  footer: ReactNode;
}

/** Sign-in / sign-up frame, following the design's email form: a light card
 * outlined in #FA4D01 with a heavier right and bottom edge. */
export function AuthShell({ title, description, children, footer }: AuthShellProps) {
  return (
    <main className="relative isolate flex min-h-screen items-center justify-center overflow-hidden bg-muted px-4 py-24 sm:px-8">
      <header className="absolute inset-x-0 top-0 z-10 mx-auto flex max-w-[1500px] items-center justify-between px-6 py-7 sm:px-10">
        <Link to="/" aria-label="PARTHA home"><BrandLogo className="w-[190px] [&_img]:w-[190px]" /></Link>
        <Link to="/" className="text-sm font-medium text-foreground underline decoration-primary underline-offset-4 hover:text-primary">Back to home</Link>
      </header>
      <section className="relative z-10 w-full max-w-[480px] rounded-xl border border-b-4 border-r-4 border-brand-orange bg-[#f3f2ef] px-4 pb-4 pt-12 shadow-[0_12px_18px_hsl(0_0%_0%/0.14)]">
        <div className="text-center">
          <BrandLogo compact className="mx-auto mb-3" />
          <h1 className="font-display text-2xl font-medium text-[#18191b]">{title}</h1>
          {description && <p className="mt-3 text-sm leading-6 text-muted-foreground">{description}</p>}
        </div>
        <div className="mt-6">{children}</div>
        <div className="mt-6 text-center text-xs text-foreground">{footer}</div>
      </section>
    </main>
  );
}
