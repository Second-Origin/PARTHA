import type { ReactNode } from 'react';
import { BrandLogo } from '@/shared/components/ui/BrandLogo';

interface AuthShellProps {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
}

export function AuthShell({ eyebrow, title, description, children, footer }: AuthShellProps) {
  return (
    <main className="relative grid min-h-screen overflow-hidden bg-background lg:grid-cols-[1.05fr_0.95fr]">
      <div aria-hidden="true" className="absolute -left-24 top-20 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
      <section className="relative hidden flex-col justify-between border-r border-border p-12 lg:flex">
        <BrandLogo />
        <div className="max-w-xl pb-14">
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-primary">Repository Intelligence</p>
          <p className="text-5xl font-semibold leading-[1.08] tracking-[-0.04em] text-foreground">
            Reveal the system behind the code.
          </p>
          <p className="mt-6 max-w-lg text-base leading-7 text-muted-foreground">
            Turn a sealed repository snapshot into evidence-backed architecture, dependencies, reviews, and documentation.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">Private repositories stay owner-scoped. AI is optional.</p>
      </section>

      <section className="relative flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <BrandLogo className="mb-10 lg:hidden" />
          <div className="partha-surface p-6 sm:p-8">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">{eyebrow}</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
            <div className="mt-7">{children}</div>
          </div>
          <div className="mt-5 text-center text-sm text-muted-foreground">{footer}</div>
        </div>
      </section>
    </main>
  );
}
