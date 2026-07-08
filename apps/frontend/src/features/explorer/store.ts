import { create } from 'zustand';
import type { FileTreeNode } from '@/shared/types';

interface ExplorerState {
  expandedFolders: Set<string>;
  toggleFolder: (id: string) => void;
  expandFolder: (id: string) => void;
  collapseAll: () => void;
  expandAll: (nodes: FileTreeNode[]) => void;

  selectedFileId: string | null;
  selectedNode: FileTreeNode | null;
  selectFile: (node: FileTreeNode) => void;
  clearSelection: () => void;

  focusedId: string | null;
  setFocusedId: (id: string | null) => void;

  searchQuery: string;
  setSearchQuery: (query: string) => void;

  explorerWidth: number;
  setExplorerWidth: (width: number) => void;

  detailsTab: 'details' | 'preview';
  setDetailsTab: (tab: 'details' | 'preview') => void;
}

export const useExplorerStore = create<ExplorerState>((set) => ({
  expandedFolders: new Set<string>(),
  toggleFolder: (id) =>
    set((state) => {
      const next = new Set(state.expandedFolders);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { expandedFolders: next };
    }),
  expandFolder: (id) =>
    set((state) => {
      const next = new Set(state.expandedFolders);
      next.add(id);
      return { expandedFolders: next };
    }),
  collapseAll: () => set({ expandedFolders: new Set() }),
  expandAll: (nodes) => {
    const ids = new Set<string>();
    function walk(list: FileTreeNode[]) {
      for (const n of list) {
        if (n.type === 'folder') {
          ids.add(n.id);
          if (n.children) walk(n.children);
        }
      }
    }
    walk(nodes);
    set({ expandedFolders: ids });
  },

  selectedFileId: null,
  selectedNode: null,
  selectFile: (node) => set({ selectedFileId: node.id, selectedNode: node }),
  clearSelection: () => set({ selectedFileId: null, selectedNode: null }),

  focusedId: null,
  setFocusedId: (id) => set({ focusedId: id }),

  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),

  explorerWidth: 280,
  setExplorerWidth: (width) => set({ explorerWidth: width }),

  detailsTab: 'details',
  setDetailsTab: (tab) => set({ detailsTab: tab }),
}));
