import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAppStore } from '@/app/store/useAppStore';
import { useToastNotifications } from '@/shared/hooks/useToastNotifications';
import { useKeyboardShortcuts } from '@/shared/hooks/useKeyboardShortcuts';
import { cn } from '@/shared/utils/cn';
import { RepositoryProvider } from '@/features/repositories/context/RepositoryProvider';

// MainLayout only ever renders inside RequireAuth's authenticated branch, so
// mounting the repository fetch here (rather than in App.tsx, above the
// router) guarantees it can't fire while the session is still initialising
// or unauthenticated — RequireAuth simply never mounts this tree until then.
export function MainLayout() {
  const { sidebarCollapsed } = useAppStore();
  useToastNotifications();
  useKeyboardShortcuts();

  return (
    <RepositoryProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div
          className={cn(
            'flex flex-1 flex-col transition-all duration-200',
            sidebarCollapsed ? 'ml-16' : 'ml-60'
          )}
        >
          <TopBar />
          <main className="flex-1 overflow-y-auto scrollbar-thin p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </RepositoryProvider>
  );
}
