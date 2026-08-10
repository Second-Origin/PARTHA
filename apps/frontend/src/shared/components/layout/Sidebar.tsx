import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useAppStore } from '@/app/store/useAppStore';
import { useAuthStore } from '@/app/store/useAuthStore';
import { primaryNavigationSurfaces, type NavigableProductSurface } from '@/app/routes/productSurfaces';
import { BrandLogo } from '@/shared/components/ui/BrandLogo';

const flagshipNavigationSurfaces = primaryNavigationSurfaces.filter((item) => item.navGroup === 'flagship');
const secondaryNavigationSurfaces = primaryNavigationSurfaces.filter((item) => item.navGroup === 'secondary');

/** One sidebar row. `muted` reduces (never removes) a secondary surface's visual weight (#176). */
function NavLink({
  item,
  isActive,
  isMobile,
  sidebarCollapsed,
  onNavigate,
  muted = false,
}: {
  item: NavigableProductSurface;
  isActive: boolean;
  isMobile: boolean;
  sidebarCollapsed: boolean;
  onNavigate: () => void;
  muted?: boolean;
}) {
  return (
    <Link
      to={item.path}
      onClick={() => {
        if (isMobile) onNavigate();
      }}
      aria-label={item.label}
      aria-current={isActive ? 'page' : undefined}
      className={cn(
        'flex min-h-9 items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors',
        muted ? 'font-normal' : 'font-medium',
        isActive
          ? 'bg-sidebar-accent text-sidebar-accent-foreground shadow-sm'
          : 'text-muted-foreground hover:bg-accent hover:text-sidebar-foreground'
      )}
    >
      <item.icon className={cn('shrink-0', muted ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
      <AnimatePresence>
        {(isMobile || !sidebarCollapsed) && (
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
}

export function Sidebar() {
  const location = useLocation();
  const {
    sidebarCollapsed,
    toggleSidebar,
    mobileSidebarOpen,
    setMobileSidebarOpen,
  } = useAppStore();
  const [isMobile, setIsMobile] = useState(false);
  const asideRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const user = useAuthStore((state) => state.user);
  const userEmail = user?.email ?? null;
  const avatarInitial = userEmail?.charAt(0).toUpperCase() ?? '?';

  useEffect(() => {
    if (!window.matchMedia) return;
    const query = window.matchMedia('(max-width: 767px)');
    const update = () => setIsMobile(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    const aside = asideRef.current;
    if (!aside) return;
    aside.inert = isMobile && !mobileSidebarOpen;
    if (!isMobile || !mobileSidebarOpen) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setMobileSidebarOpen(false);
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = Array.from(
        aside.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => !element.inert && element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [isMobile, mobileSidebarOpen, setMobileSidebarOpen]);

  return (
    <>
      {mobileSidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation drawer"
          onClick={() => setMobileSidebarOpen(false)}
          className="fixed inset-0 z-40 bg-background/70 md:hidden"
        />
      )}
      <motion.aside
        ref={asideRef}
        role={isMobile ? 'dialog' : undefined}
        aria-label={isMobile ? 'Navigation drawer' : 'Primary navigation'}
        aria-modal={isMobile && mobileSidebarOpen ? 'true' : undefined}
        initial={false}
        animate={{ width: sidebarCollapsed ? 64 : 204 }}
        transition={{ duration: 0.2, ease: 'easeInOut' }}
        className={cn(
          'fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-sidebar-border bg-sidebar max-md:!w-[min(82vw,260px)] max-md:transition-transform max-md:duration-200',
          mobileSidebarOpen ? 'max-md:translate-x-0' : 'max-md:-translate-x-full',
        )}
      >
      <div className="flex h-16 items-center justify-between gap-2 px-3">
        <Link to="/" className="flex min-w-0 items-center overflow-hidden">
          <AnimatePresence>
            <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="block overflow-hidden whitespace-nowrap"
              >
                <BrandLogo compact={!isMobile && sidebarCollapsed} />
              </motion.span>
          </AnimatePresence>
        </Link>
        <button
          ref={closeButtonRef}
          onClick={() => {
            if (isMobile) setMobileSidebarOpen(false);
            else toggleSidebar();
          }}
          aria-label={
            isMobile
              ? 'Close navigation drawer'
              : sidebarCollapsed
                ? 'Expand sidebar'
                : 'Collapse sidebar'
          }
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
        >
          <ChevronLeft
            className={cn('h-4 w-4 transition-transform duration-200', sidebarCollapsed && 'rotate-180')}
          />
        </button>
      </div>

      <nav aria-label="Primary navigation" className="flex-1 space-y-1 overflow-y-auto px-2 py-3 scrollbar-thin">
        {flagshipNavigationSurfaces.map((item) => (
          <NavLink
            key={item.path}
            item={item}
            isActive={location.pathname === item.path}
            isMobile={isMobile}
            sidebarCollapsed={sidebarCollapsed}
            onNavigate={() => setMobileSidebarOpen(false)}
          />
        ))}

        {secondaryNavigationSurfaces.length > 0 && (
          <>
            <AnimatePresence>
              {(isMobile || !sidebarCollapsed) && (
                <motion.p
                  data-testid="secondary-navigation-label"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="px-2.5 pb-1 pt-3 text-2xs font-medium uppercase tracking-wide text-muted-foreground/70"
                >
                  More
                </motion.p>
              )}
            </AnimatePresence>
            {secondaryNavigationSurfaces.map((item) => (
              <NavLink
                key={item.path}
                item={item}
                isActive={location.pathname === item.path}
                isMobile={isMobile}
                sidebarCollapsed={sidebarCollapsed}
                onNavigate={() => setMobileSidebarOpen(false)}
                muted
              />
            ))}
          </>
        )}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        <div className={cn('flex items-center gap-3 rounded-md px-2.5 py-2', sidebarCollapsed && !isMobile && 'justify-center')}>
          <div className="h-7 w-7 shrink-0 rounded-full bg-primary/20 flex items-center justify-center">
            <span className="text-xs font-medium text-primary">{avatarInitial}</span>
          </div>
          <AnimatePresence>
            {(isMobile || !sidebarCollapsed) && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden"
              >
                <p className="text-xs font-medium text-sidebar-foreground truncate">
                  {userEmail ?? 'Account identity unavailable'}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      </motion.aside>
    </>
  );
}
