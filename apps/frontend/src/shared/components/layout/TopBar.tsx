import { useNavigate } from 'react-router-dom';
import {
  Search,
  Upload,
  Bell,
  BadgeCheck,
  ChevronDown,
  User,
  LogOut,
  Settings,
  Loader2,
  Ban,
  Menu,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useAppStore } from '@/app/store/useAppStore';
import { useAuthStore } from '@/app/store/useAuthStore';
import { useState, useRef, useEffect } from 'react';
import { useRepository } from '@/features/repositories/hooks/useRepository';
import type { FileTreeNode } from '@/shared/types';
import { buildSearchResultDestination } from './searchNavigation';

export function TopBar() {
  const navigate = useNavigate();
  const {
    notifications,
    markNotificationRead,
    searchQuery,
    setSearchQuery,
    searchOpen,
    setSearchOpen,
    setMobileSidebarOpen,
  } = useAppStore();
  const { repositories, activeRepository, selectRepository } = useRepository();
  const logout = useAuthStore((state) => state.logout);
  const [signingOut, setSigningOut] = useState(false);

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
      navigate('/login', { replace: true });
    }
  };

  const [repoDropdownOpen, setRepoDropdownOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const repoRef = useRef<HTMLDivElement>(null);
  const repoTriggerRef = useRef<HTMLButtonElement>(null);
  const repoMenuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const unreadCount = notifications.filter((n) => !n.read).length;
  const searchResults = searchQuery.trim()
    ? repositories.flatMap((repo) => {
        const q = searchQuery.trim().toLowerCase();
        const repoMatch = repo.name.toLowerCase().includes(q)
          ? [{ type: 'repository' as const, repo, label: repo.name, path: '' }]
          : [];
        const fileMatches = flattenFiles(repo.fileTree)
          .filter((file) => file.path.toLowerCase().includes(q))
          .slice(0, 6)
          .map((file) => ({ type: 'file' as const, repo, label: file.name, path: file.path }));
        return [...repoMatch, ...fileMatches];
      }).slice(0, 8)
    : [];

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (repoRef.current && !repoRef.current.contains(e.target as Node)) setRepoDropdownOpen(false);
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
      if (userRef.current && !userRef.current.contains(e.target as Node)) setUserMenuOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (searchOpen) {
      searchRef.current?.focus();
      setSearchOpen(false);
    }
  }, [searchOpen, setSearchOpen]);

  useEffect(() => {
    if (!repoDropdownOpen) return;
    const options = Array.from(
      repoMenuRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? [],
    );
    (options.find((option) => option.getAttribute('aria-selected') === 'true') ?? options[0])?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setRepoDropdownOpen(false);
        repoTriggerRef.current?.focus();
        return;
      }
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) || options.length === 0) return;
      event.preventDefault();
      const current = options.indexOf(document.activeElement as HTMLButtonElement);
      const next =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? options.length - 1
            : event.key === 'ArrowDown'
              ? (current + 1 + options.length) % options.length
              : (current - 1 + options.length) % options.length;
      options[next]?.focus();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [repoDropdownOpen]);

  const statusIcon = (status: string) => {
    if (status === 'completed') return <BadgeCheck aria-label="Analysed" className="h-5 w-5 shrink-0 fill-success text-white" />;
    if (status === 'analysing') return <Loader2 aria-label="Analysing" className="h-4 w-4 shrink-0 animate-spin text-primary" />;
    if (status === 'cancelled') return <Ban aria-label="Cancelled" className="h-4 w-4 shrink-0 text-muted-foreground" />;
    return null;
  };

  return (
    <header className="sticky top-0 z-30 flex h-20 min-w-0 shrink-0 items-center justify-between gap-2 border-b border-border bg-muted px-3 sm:h-[109px] sm:items-start sm:pl-[35px] sm:pr-[51px] sm:pt-12">
      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-[35px]">
        <button
          type="button"
          onClick={() => setMobileSidebarOpen(true)}
          aria-label="Open navigation drawer"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-primary/20 text-muted-foreground hover:bg-accent md:hidden"
        >
          <Menu className="h-4 w-4" />
        </button>
        <div ref={repoRef} className="relative">
          <button
            ref={repoTriggerRef}
            type="button"
            aria-haspopup="listbox"
            aria-expanded={repoDropdownOpen}
            aria-controls="repository-selector-options"
            onClick={() => setRepoDropdownOpen(!repoDropdownOpen)}
            className="flex h-9 w-[140px] items-center justify-between gap-2 rounded-md border border-brand-orange bg-white px-2 text-base text-foreground shadow-[0_2px_4px_hsl(0_0%_0%/0.15)] transition-colors hover:bg-card sm:w-[222px]"
          >
            <span className="truncate">
              {activeRepository ? activeRepository.name : 'No repository'}
            </span>
            <ChevronDown className={cn('h-4 w-4 shrink-0 transition-transform', repoDropdownOpen && 'rotate-180')} />
          </button>
          {repoDropdownOpen && (
            <div
              ref={repoMenuRef}
              id="repository-selector-options"
              role="listbox"
              aria-label="Repositories"
              className="absolute left-0 top-full z-50 mt-1 w-[290px] rounded-md border border-brand-orange bg-popover shadow-[0_2px_4px_hsl(0_0%_0%/0.15)] animate-scale-in"
            >
              <div className="space-y-1 p-1.5">
                {repositories.length === 0 ? (
                  <p className="px-3 py-2 text-sm text-muted-foreground">No repositories uploaded</p>
                ) : (
                  repositories.map((repo) => (
                    <button
                      key={repo.id}
                      type="button"
                      role="option"
                      aria-selected={activeRepository?.id === repo.id}
                      onClick={() => {
                        selectRepository(repo);
                        setRepoDropdownOpen(false);
                        repoTriggerRef.current?.focus();
                      }}
                      className={cn(
                        'flex w-full items-center justify-between gap-3 rounded-md px-2 py-1 text-left text-lg transition-colors hover:bg-accent',
                        activeRepository?.id === repo.id && 'bg-[#f3ceb9] hover:bg-[#f3ceb9]'
                      )}
                    >
                      <span className="truncate">{repo.name}</span>
                      {statusIcon(repo.status)}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <div className="relative hidden max-w-[662px] flex-1 md:block">
          <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/70" />
          <input
            ref={searchRef}
            type="text"
            placeholder="Search... (Ctrl+K)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-md border border-brand-orange bg-white pl-10 pr-3 text-base text-foreground shadow-[0_2px_4px_hsl(0_0%_0%/0.15)] placeholder:text-muted-foreground"
          />
          {searchQuery.trim() && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-md border border-brand-orange bg-popover p-1.5 shadow-[0_2px_4px_hsl(0_0%_0%/0.15)] animate-scale-in">
              {searchResults.length === 0 ? (
                <p className="px-3 py-2 text-sm text-muted-foreground">No matches found</p>
              ) : (
                searchResults.map((result) => (
                  <button
                    key={`${result.repo.id}-${result.type}-${result.path || result.label}`}
                    onClick={() => {
                      selectRepository(result.repo);
                      setSearchQuery('');
                      navigate(buildSearchResultDestination(result.repo.id, result));
                    }}
                    className="w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-accent"
                  >
                    <p className="text-sm text-foreground truncate">{result.label}</p>
                    <p className="text-2xs text-muted-foreground truncate">
                      {result.type === 'repository' ? 'Repository' : `${result.repo.name}${result.path}`}
                    </p>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-6">
        <button
          onClick={() => navigate('/upload')}
          className="flex h-9 items-center justify-center gap-2 rounded-md bg-brand-blue px-3 text-base text-white transition-colors hover:bg-brand-blue/90 sm:w-[122px]"
        >
          <Upload className="h-4 w-4" />
          <span className="hidden sm:inline">Upload</span>
        </button>

        <div ref={notifRef} className="relative hidden sm:block">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            data-testid="notification-menu-trigger"
            aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
            aria-haspopup="true"
            aria-expanded={notifOpen}
            className="relative flex h-9 w-9 items-center justify-center rounded-full text-foreground transition-colors hover:bg-card"
          >
            <Bell aria-hidden="true" focusable="false" className="h-6 w-6" />
            {unreadCount > 0 && (
              <span aria-hidden="true" className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-brand-orange" />
            )}
          </button>
          {notifOpen && (
            <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-md border border-brand-orange bg-popover shadow-[0_2px_4px_hsl(0_0%_0%/0.15)] animate-scale-in">
              <div className="p-3 border-b border-border flex items-center justify-between">
                <h3 className="text-sm font-medium">Notifications</h3>
                {unreadCount > 0 && (
                  <span className="text-2xs text-muted-foreground">{unreadCount} unread</span>
                )}
              </div>
              <div className="p-2 max-h-64 overflow-y-auto scrollbar-thin">
                {notifications.length === 0 ? (
                  <p className="px-3 py-4 text-sm text-muted-foreground text-center">No notifications</p>
                ) : (
                  notifications.map((notif) => (
                    <button
                      key={notif.id}
                      onClick={() => markNotificationRead(notif.id)}
                      className={cn(
                        'w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-accent',
                        !notif.read && 'bg-accent/50'
                      )}
                    >
                      <p className="text-sm font-medium text-foreground">{notif.title}</p>
                      <p className="text-xs text-muted-foreground">{notif.message}</p>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <div ref={userRef} className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            data-testid="user-menu-trigger"
            aria-label="Account menu"
            aria-haspopup="true"
            aria-expanded={userMenuOpen}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-orange/20 text-foreground transition-colors hover:bg-brand-orange/30"
          >
            <User aria-hidden="true" focusable="false" className="h-5 w-5" />
          </button>
          {userMenuOpen && (
            <div className="absolute right-0 top-full z-50 mt-2 w-48 rounded-md border border-brand-orange bg-popover shadow-[0_2px_4px_hsl(0_0%_0%/0.15)] animate-scale-in">
              <div className="p-1">
                <button
                  onClick={() => {
                    navigate('/settings');
                    setUserMenuOpen(false);
                  }}
                  className="w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent transition-colors"
                >
                  <Settings className="h-4 w-4" /> Settings
                </button>
                <button
                  onClick={handleSignOut}
                  disabled={signingOut}
                  className="w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-accent disabled:opacity-50 transition-colors"
                >
                  <LogOut className="h-4 w-4" /> {signingOut ? 'Signing out...' : 'Sign Out'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function flattenFiles(nodes: FileTreeNode[]): { name: string; path: string }[] {
  const files: { name: string; path: string }[] = [];
  for (const node of nodes) {
    if (node.type === 'file') files.push({ name: node.name, path: node.path });
    if (node.children) files.push(...flattenFiles(node.children));
  }
  return files;
}
