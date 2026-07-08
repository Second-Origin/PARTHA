import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAppStore } from '@/store/useAppStore';
import { useToastNotifications } from '@/hooks/useToastNotifications';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { cn } from '@/utils/cn';

export function MainLayout() {
  const { sidebarCollapsed } = useAppStore();
  useToastNotifications();
  useKeyboardShortcuts();

  return (
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
  );
}
