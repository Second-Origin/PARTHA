import { create } from 'zustand';
import type { ArchitectureModel } from '@/types/architecture';
import type { HeatmapMode } from '@/types/architecture';

interface ArchitectureState {
  model: ArchitectureModel | null;
  setModel: (model: ArchitectureModel) => void;

  selectedNodeId: string | null;
  setSelectedNodeId: (id: string | null) => void;

  highlightedNodeIds: Set<string>;
  setHighlightedNodeIds: (ids: Set<string>) => void;

  searchQuery: string;
  setSearchQuery: (query: string) => void;

  expandedModules: Set<string>;
  toggleModule: (id: string) => void;

  showMiniMap: boolean;
  setShowMiniMap: (show: boolean) => void;

  showGrid: boolean;
  setShowGrid: (show: boolean) => void;

  activeTab: 'graph' | 'request-flow' | 'heatmap';
  setActiveTab: (tab: 'graph' | 'request-flow' | 'heatmap') => void;

  inspectorOpen: boolean;
  setInspectorOpen: (open: boolean) => void;

  explorerOpen: boolean;
  setExplorerOpen: (open: boolean) => void;

  heatmapMode: HeatmapMode;
  setHeatmapMode: (mode: HeatmapMode) => void;

  bookmarkedNodes: Set<string>;
  toggleBookmark: (id: string) => void;

  hiddenNodes: Set<string>;
  hideNode: (id: string) => void;
  showAllNodes: () => void;

  isolatedSubtree: string | null;
  setIsolatedSubtree: (id: string | null) => void;

  contextMenuTarget: string | null;
  contextMenuPosition: { x: number; y: number } | null;
  openContextMenu: (nodeId: string, position: { x: number; y: number }) => void;
  closeContextMenu: () => void;

  bottomPanelOpen: boolean;
  setBottomPanelOpen: (open: boolean) => void;
}

export const useArchitectureStore = create<ArchitectureState>((set) => ({
  model: null,
  setModel: (model) => set({ model }),

  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id, inspectorOpen: !!id }),

  highlightedNodeIds: new Set(),
  setHighlightedNodeIds: (ids) => set({ highlightedNodeIds: ids }),

  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),

  expandedModules: new Set(['presentation', 'business-logic', 'domain', 'infrastructure']),
  toggleModule: (id) =>
    set((state) => {
      const next = new Set(state.expandedModules);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { expandedModules: next };
    }),

  showMiniMap: true,
  setShowMiniMap: (show) => set({ showMiniMap: show }),

  showGrid: true,
  setShowGrid: (show) => set({ showGrid: show }),

  activeTab: 'graph',
  setActiveTab: (tab) => set({ activeTab: tab }),

  inspectorOpen: false,
  setInspectorOpen: (open) => set({ inspectorOpen: open }),

  explorerOpen: true,
  setExplorerOpen: (open) => set({ explorerOpen: open }),

  heatmapMode: 'none',
  setHeatmapMode: (mode) => set({ heatmapMode: mode }),

  bookmarkedNodes: new Set(),
  toggleBookmark: (id) =>
    set((state) => {
      const next = new Set(state.bookmarkedNodes);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { bookmarkedNodes: next };
    }),

  hiddenNodes: new Set(),
  hideNode: (id) =>
    set((state) => {
      const next = new Set(state.hiddenNodes);
      next.add(id);
      return { hiddenNodes: next };
    }),
  showAllNodes: () => set({ hiddenNodes: new Set() }),

  isolatedSubtree: null,
  setIsolatedSubtree: (id) => set({ isolatedSubtree: id }),

  contextMenuTarget: null,
  contextMenuPosition: null,
  openContextMenu: (nodeId, position) => set({ contextMenuTarget: nodeId, contextMenuPosition: position }),
  closeContextMenu: () => set({ contextMenuTarget: null, contextMenuPosition: null }),

  bottomPanelOpen: false,
  setBottomPanelOpen: (open) => set({ bottomPanelOpen: open }),
}));
