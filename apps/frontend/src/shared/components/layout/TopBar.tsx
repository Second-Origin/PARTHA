import { useNavigate } from 'react-router-dom';
import {
  Search,
  Upload,
  Github,
  Bell,
  ChevronDown,
  User,
  LogOut,
  Settings,
  Check,
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
    if (status === 'completed') return <Check className="h-3 w-3 text-success" />;
    if (status === 'analysing') return <Loader2 className="h-3 w-3 text-primary animate-spin" />;
    if (status === 'cancelled') return <Ban className="h-3 w-3 text-muted-foreground" />;
    return null;
  };

  return (
    <header className="sticky top-0 z-30 flex h-20 min-w-0 items-center justify-between gap-2 border-b border-primary/15 bg-background/95 px-3 backdrop-blur-sm sm:h-24 sm:px-7">
      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
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
            className="flex max-w-[140px] items-center gap-2 rounded-xl border border-primary/20 bg-card px-3 py-2.5 text-sm transition-colors hover:bg-accent sm:max-w-[230px]"
          >
            <span className="text-muted-foreground truncate">
              {activeRepository ? activeRepository.name : 'No repository'}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          </button>
          {repoDropdownOpen && (
            <div
              ref={repoMenuRef}
              id="repository-selector-options"
              role="listbox"
              aria-label="Repositories"
              className="absolute top-full left-0 mt-2 w-64 rounded-2xl border border-primary/20 bg-popover shadow-lg animate-scale-in z-50"
            >
              <div className="p-2">
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
                        'w-full flex items-center justify-between rounded-xl px-3 py-2 text-sm text-left hover:bg-accent transition-colors',
                        activeRepository?.id === repo.id && 'bg-accent'
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

        <div className="relative hidden max-w-md flex-1 md:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            ref={searchRef}
            type="text"
            placeholder="Search... (Ctrl+K)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="partha-input w-full py-2 pl-9 pr-3 text-sm transition-shadow"
          />
          {searchQuery.trim() && (
            <div className="absolute top-full left-0 right-0 mt-2 rounded-2xl border border-primary/20 bg-popover shadow-lg animate-scale-in z-50 p-2">
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
                    className="w-full rounded-xl px-3 py-2 text-left hover:bg-accent transition-colors"
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

      <div className="flex items-center gap-2">
        <button
          onClick={() => navigate('/upload')}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-[0_8px_18px_rgba(250,77,1,0.18)] hover:bg-primary/90 transition-colors"
        >
          <Upload className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Upload</span>
        </button>

        <button
          onClick={() => activeRepository?.sourceUrl && window.open(activeRepository.sourceUrl, '_blank', 'noopener,noreferrer')}
          disabled={!activeRepository?.sourceUrl}
          title={activeRepository?.sourceUrl ? 'Open repository source' : 'No GitHub URL available'}
          className="hidden h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40 sm:flex"
        >
          <Github className="h-4 w-4" />
        </button>

        <div ref={notifRef} className="relative hidden sm:block">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            data-testid="notification-menu-trigger"
            aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
            aria-haspopup="true"
            aria-expanded={notifOpen}
            className="relative flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <Bell aria-hidden="true" focusable="false" className="h-4 w-4" />
            {unreadCount > 0 && (
              <span aria-hidden="true" className="absolute top-1 right-1 h-2 w-2 rounded-full bg-primary" />
            )}
          </button>
          {notifOpen && (
            <div className="absolute top-full right-0 mt-2 w-80 rounded-2xl border border-primary/20 bg-popover shadow-lg animate-scale-in z-50">
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
                        'w-full text-left px-3 py-2 rounded-xl hover:bg-accent transition-colors',
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
            className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-[0_6px_14px_rgba(250,77,1,0.18)] hover:bg-primary/90 transition-colors"
          >
            <User aria-hidden="true" focusable="false" className="h-4 w-4" />
          </button>
          {userMenuOpen && (
            <div className="absolute top-full right-0 mt-2 w-48 rounded-2xl border border-primary/20 bg-popover shadow-lg animate-scale-in z-50">
              <div className="p-1">
                <button
                  onClick={() => {
                    navigate('/settings');
                    setUserMenuOpen(false);
                  }}
                  className="w-full flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-accent transition-colors"
                >
                  <Settings className="h-4 w-4" /> Settings
                </button>
                <button
                  onClick={handleSignOut}
                  disabled={signingOut}
                  className="w-full flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-destructive hover:bg-accent disabled:opacity-50 transition-colors"
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
