import { RouterProvider } from 'react-router-dom';
import { Toaster } from 'sonner';
import { router } from '@/routes/router';
import { RepositoryProvider } from '@/features/repositories/context/RepositoryProvider';

export function App() {
  return (
    <RepositoryProvider>
      <RouterProvider router={router} />
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            color: 'hsl(var(--foreground))',
          },
        }}
      />
    </RepositoryProvider>
  );
}
