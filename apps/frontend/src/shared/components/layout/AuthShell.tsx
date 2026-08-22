import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
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
    <main className="relative isolate flex min-h-screen items-center justify-center overflow-hidden bg-muted px-4 py-24 sm:px-8">
      <div aria-hidden="true" className="absolute -left-20 top-24 h-[28rem] w-[28rem] rounded-full bg-primary/10 blur-3xl" />
      <div aria-hidden="true" className="absolute -right-28 bottom-10 h-[30rem] w-[30rem] rounded-full bg-[#006298]/10 blur-3xl" />
      <header className="absolute inset-x-0 top-0 z-10 mx-auto flex max-w-[1500px] items-center justify-between px-6 py-7 sm:px-10">
        <Link to="/" aria-label="PARTHA home"><BrandLogo className="w-[190px] [&_img]:w-[190px]" /></Link>
        <Link to="/" className="text-sm font-medium text-foreground underline decoration-primary underline-offset-4 hover:text-primary">Back to home</Link>
      </header>
      <section className="relative z-10 w-full max-w-[500px] rounded-[2rem] border border-primary border-b-4 border-l-4 border-r-4 bg-card/90 p-6 shadow-[0_12px_18px_hsl(var(--foreground)/0.14)] sm:p-9">
        <div className="mx-auto max-w-[410px] text-center">
          <BrandLogo compact className="mx-auto mb-4 w-12" />
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">{eyebrow}</p>
          <h1 className="mt-3 text-3xl font-medium tracking-[-0.05em] text-foreground">{title}</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        <div className="mx-auto mt-8 max-w-[410px]">{children}</div>
        <div className="mx-auto mt-6 max-w-[410px] text-center text-sm text-muted-foreground">{footer}</div>
      </section>
    </main>
  );
}
