import { useEffect } from 'react';
import { useAppStore } from '@/app/store/useAppStore';

export function useKeyboardShortcuts() {
  const setSearchOpen = useAppStore((s) => s.setSearchOpen);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === 'Escape') {
        setSearchOpen(false);
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [setSearchOpen]);
}
