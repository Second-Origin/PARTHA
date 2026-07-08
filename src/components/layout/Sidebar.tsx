import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  FolderGit2,
  Upload,
  Network,
  GitBranch,
  Bot,
  FileText,
  Lightbulb,
  Settings,
  ChevronLeft,
  Hexagon,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useAppStore } from '@/store/useAppStore';

const navItems = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { label: 'Repositories', icon: FolderGit2, path: '/repositories' },
  { label: 'Upload Repository', icon: Upload, path: '/upload' },
  { label: 'Architecture', icon: Network, path: '/architecture' },
  { label: 'Engineering Review', icon: ShieldCheck, path: '/review' },
  { label: 'Dependency Graph', icon: GitBranch, path: '/dependencies' },
  { label: 'AI Workspace', icon: Bot, path: '/ai-workspace' },
  { label: 'Documentation', icon: FileText, path: '/documentation' },
  { label: 'Insights', icon: Lightbulb, path: '/insights' },
  { label: 'Settings', icon: Settings, path: '/settings' },
];

export function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarCollapsed ? 64 : 240 }}
      transition={{ duration: 0.2, ease: 'easeInOut' }}
      className="fixed left-0 top-0 z-40 h-screen flex flex-col border-r border-sidebar-border bg-sidebar"
    >
      <div className="flex h-14 items-center justify-between px-3">
        <Link to="/" className="flex items-center gap-2 overflow-hidden">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Hexagon className="h-4 w-4" />
          </div>
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="text-sm font-semibold text-sidebar-foreground whitespace-nowrap"
              >
                PARTHA
              </motion.span>
            )}
          </AnimatePresence>
        </Link>
        <button
          onClick={toggleSidebar}
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
        >
          <ChevronLeft
            className={cn('h-4 w-4 transition-transform duration-200', sidebarCollapsed && 'rotate-180')}
          />
        </button>
      </div>

      <nav className="flex-1 space-y-1 px-2 py-2 overflow-y-auto scrollbar-thin">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <AnimatePresence>
                {!sidebarCollapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="whitespace-nowrap"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        <div className={cn('flex items-center gap-3 rounded-md px-2.5 py-2', sidebarCollapsed && 'justify-center')}>
          <div className="h-7 w-7 shrink-0 rounded-full bg-primary/20 flex items-center justify-center">
            <span className="text-xs font-medium text-primary">P</span>
          </div>
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden"
              >
                <p className="text-xs font-medium text-sidebar-foreground truncate">Developer</p>
                <p className="text-2xs text-muted-foreground truncate">Free Plan</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.aside>
  );
}
