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
const analysisNavigationSurfaces = primaryNavigationSurfaces.filter((item) => item.navGroup === 'analysis');
const assistNavigationSurfaces = primaryNavigationSurfaces.filter((item) => item.navGroup === 'assist');
// `filter`, not `find`: a second utility surface must not silently disappear
// from navigation just because it was registered after Settings.
const utilityNavigationSurfaces = primaryNavigationSurfaces.filter((item) => item.navGroup === 'utility');

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
        'flex min-h-10 items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors',
        muted ? 'font-normal' : 'font-medium',
        isActive
          ? 'bg-[#fa4d01] text-white shadow-[0_8px_18px_rgba(250,77,1,0.18)]'
          : 'text-sidebar-foreground/70 hover:bg-[#fa4d01]/10 hover:text-sidebar-foreground'
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

/** A labelled, muted group of nav rows (e.g. Analysis, Assist) -- header hides accessibly when collapsed, links never do (#289). */
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
            className="px-3 pb-1 pt-5 text-2xs font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/45"
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
          'fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-[#fa4d01]/20 bg-[#f3f0e9] max-md:!w-[min(82vw,280px)] max-md:transition-transform max-md:duration-200',
          mobileSidebarOpen ? 'max-md:translate-x-0' : 'max-md:-translate-x-full',
        )}
      >
      <div className="flex h-24 items-center justify-between gap-2 px-4">
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
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#fa4d01]/20 text-sidebar-foreground/60 hover:bg-[#fa4d01] hover:text-white transition-colors"
        >
          <ChevronLeft
            className={cn('h-4 w-4 transition-transform duration-200', sidebarCollapsed && 'rotate-180')}
          />
        </button>
      </div>

      <nav aria-label="Primary navigation" className="flex-1 space-y-1 overflow-y-auto px-3 py-4 scrollbar-thin">
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
          label="Analysis"
          testId="analysis-navigation-label"
          items={analysisNavigationSurfaces}
          isMobile={isMobile}
          sidebarCollapsed={sidebarCollapsed}
          location={location}
          onNavigate={() => setMobileSidebarOpen(false)}
        />

        <NavSection
          label="Assist"
          testId="assist-navigation-label"
          items={assistNavigationSurfaces}
          isMobile={isMobile}
          sidebarCollapsed={sidebarCollapsed}
          location={location}
          onNavigate={() => setMobileSidebarOpen(false)}
        />
      </nav>

      <div className="border-t border-[#fa4d01]/15 p-3">
        {/* Pinned out of the scrollable list, but still inside a navigation
            landmark of its own: moving Settings into a bare <div> would drop
            it from landmark-based screen-reader navigation entirely (#289). */}
        {utilityNavigationSurfaces.length > 0 && (
          <nav aria-label="Settings" className="border-b border-[#fa4d01]/15 pb-3 mb-3 space-y-1">
            {utilityNavigationSurfaces.map((item) => (
              <NavLink
                key={item.path}
                item={item}
                isActive={location.pathname === item.path}
                isMobile={isMobile}
                sidebarCollapsed={sidebarCollapsed}
                onNavigate={() => setMobileSidebarOpen(false)}
              />
            ))}
          </nav>
        )}
        <div className={cn('flex items-center gap-3 rounded-xl px-3 py-2.5', sidebarCollapsed && !isMobile && 'justify-center')}>
          <div className="h-8 w-8 shrink-0 rounded-full bg-[#fa4d01] flex items-center justify-center">
            <span className="text-xs font-semibold text-white">{avatarInitial}</span>
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
