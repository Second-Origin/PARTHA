import { useState } from 'react';
import { Hero } from '@/components/Hero';
import { SimulationDemo } from '@/components/SimulationDemo';
import { RunItYourself } from '@/components/RunItYourself';
import { WaitlistForm } from '@/components/WaitlistForm';
import { Footer } from '@/components/Footer';

export function App() {
  const [waitlistOpen, setWaitlistOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Hero onJoinWaitlist={() => setWaitlistOpen(true)} />
      <main>
        <SimulationDemo />
        <div className="mx-auto max-w-5xl px-6 sm:px-8">
          <div className="h-px bg-border" />
        </div>
        <RunItYourself />
      </main>
      <Footer />
      {waitlistOpen && <WaitlistForm onClose={() => setWaitlistOpen(false)} />}
    </div>
  );
}
