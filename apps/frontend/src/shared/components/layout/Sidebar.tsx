import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useAppStore } from '@/app/store/useAppStore';
import { useAuthStore } from '@/app/store/useAuthStore';
import { primaryNavigationSurfaces, type NavigableProductSurface } from '@/app/routes/productSurfaces';
import { BrandLogo } from '@/shared/components/ui/BrandLogo';

const flagshipNavigationSurfaces = primaryNavigationSurfaces.filter((item) => item.navGroup === 'flagship');
const moreNavigationSurfaces = primaryNavigationSurfaces.filter((item) => item.navGroup === 'more');

/** One sidebar row. `muted` reduces (never removes) a lower-emphasis surface's visual weight (#176). */
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
        'flex h-9 items-center gap-3 rounded-md px-2.5 text-[19px] leading-none transition-colors',
        muted ? 'font-normal' : 'font-medium',
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-sidebar-foreground hover:bg-card'
      )}
    >
      <item.icon className={cn('shrink-0', muted ? 'h-3.5 w-3.5' : 'h-4 w-4', !isActive && 'text-sidebar-foreground/70')} />
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

/** A labelled, muted group of nav rows ("More") -- header hides accessibly when collapsed, links never do (#289). */
function NavSection({
  label,
  testId,
  items,
  isMobile,
  sidebarCollapsed,
  location,
  onNavigate,
}: {
  label: string;
  testId: string;
  items: readonly NavigableProductSurface[];
  isMobile: boolean;
  sidebarCollapsed: boolean;
  location: ReturnType<typeof useLocation>;
  onNavigate: () => void;
}) {
  if (items.length === 0) return null;
  return (
    <>
      <AnimatePresence>
        {(isMobile || !sidebarCollapsed) && (
          <motion.p
            data-testid={testId}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="px-2.5 pb-[18px] pt-[30px] text-[19px] font-normal uppercase leading-none tracking-[0.06em] text-muted-foreground"
          >
            {label}
          </motion.p>
        )}
      </AnimatePresence>
      {items.map((item) => (
        <NavLink
          key={item.path}
          item={item}
          isActive={location.pathname === item.path}
          isMobile={isMobile}
          sidebarCollapsed={sidebarCollapsed}
          onNavigate={onNavigate}
          muted
        />
      ))}
    </>
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
        animate={{ width: sidebarCollapsed ? 72 : 248 }}
        transition={{ duration: 0.2, ease: 'easeInOut' }}
        className={cn(
          'fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-sidebar-border bg-sidebar max-md:!w-[min(82vw,280px)] max-md:transition-transform max-md:duration-200',
          mobileSidebarOpen ? 'max-md:translate-x-0' : 'max-md:-translate-x-full',
        )}
      >
      <div className="flex h-20 shrink-0 items-center justify-between gap-2 px-2.5 sm:h-[109px] sm:items-start sm:pt-11">
        <Link to="/dashboard" className="flex min-w-0 items-center overflow-hidden">
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
          className="group relative flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-sidebar-foreground transition-colors hover:bg-card"
        >
          {sidebarCollapsed && !isMobile ? (
            <PanelLeftOpen aria-hidden="true" className="h-6 w-6" />
          ) : (
            <PanelLeftClose aria-hidden="true" className="h-6 w-6" />
          )}
          {!isMobile && (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute left-1/2 top-full z-10 mt-1 -translate-x-1/2 whitespace-nowrap rounded-sm bg-card px-1.5 py-0.5 text-xs text-sidebar-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
            >
              {sidebarCollapsed ? 'Show Sidebar' : 'Hide Sidebar'}
            </span>
          )}
        </button>
      </div>

      <nav aria-label="Primary navigation" className="flex-1 space-y-1 overflow-y-auto px-2.5 pb-4 pt-3.5 scrollbar-thin">
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

        <NavSection
          label="More"
          testId="more-navigation-label"
          items={moreNavigationSurfaces}
          isMobile={isMobile}
          sidebarCollapsed={sidebarCollapsed}
          location={location}
          onNavigate={() => setMobileSidebarOpen(false)}
        />
      </nav>

      <div className="shrink-0 border-t border-sidebar-border px-4 py-3">
        <div className={cn('flex items-center gap-1', sidebarCollapsed && !isMobile && 'justify-center')}>
          <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full bg-brand-orange/20">
            <span className="font-display text-sm font-semibold text-brand-plum">{avatarInitial}</span>
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
                <p className="truncate text-xs text-muted-foreground">
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
