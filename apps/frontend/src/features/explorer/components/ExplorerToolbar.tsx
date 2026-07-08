import { Search, X, FolderMinus, FolderPlus } from 'lucide-react';
import { useExplorerStore } from '../store';
import type { FileTreeNode } from '@/shared/types';

interface ExplorerToolbarProps {
  fileTree: FileTreeNode[];
}

export function ExplorerToolbar({ fileTree }: ExplorerToolbarProps) {
  const { searchQuery, setSearchQuery, collapseAll, expandAll } = useExplorerStore();

  return (
    <div className="p-2 border-b border-border space-y-2">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search files, folders..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-md border border-border bg-background pl-8 pr-8 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => expandAll(fileTree)}
          title="Expand All"
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          <FolderPlus className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={collapseAll}
          title="Collapse All"
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          <FolderMinus className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
