import { create } from 'zustand';
import type { Repository, Notification, AnalysisStage } from '@/shared/types';

interface AppState {
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;

  repositories: Repository[];
  activeRepositoryId: string | null;
  setActiveRepositoryId: (id: string | null) => void;
  addRepository: (repo: Repository) => void;
  setRepositories: (repos: Repository[]) => void;
  updateRepository: (id: string, updates: Partial<Repository>) => void;
  removeRepository: (id: string) => void;

  analysisRunning: boolean;
  currentAnalysisId: string | null;
  startAnalysis: (repoId: string) => void;
  advanceAnalysisStage: (repoId: string, stage: AnalysisStage, progress: number) => void;
  completeAnalysis: (repoId: string, updates?: Partial<Repository>) => void;
  failAnalysis: (repoId: string, error: string) => void;
  cancelAnalysis: () => void;

  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id' | 'createdAt' | 'read'>) => void;
  markNotificationRead: (id: string) => void;
  clearNotifications: () => void;

  searchQuery: string;
  setSearchQuery: (query: string) => void;
  searchOpen: boolean;
  setSearchOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  sidebarCollapsed: false,
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  repositories: [],
  activeRepositoryId: null,
  setActiveRepositoryId: (id) => set({ activeRepositoryId: id }),
  addRepository: (repo) => set((state) => ({ repositories: [...state.repositories, repo] })),
  setRepositories: (repos) =>
    set((state) => ({
      repositories: repos,
      activeRepositoryId:
        state.activeRepositoryId && repos.some((repo) => repo.id === state.activeRepositoryId)
          ? state.activeRepositoryId
          : repos[0]?.id || null,
    })),
  updateRepository: (id, updates) =>
    set((state) => {
      const repositories = state.repositories.map((r) => (r.id === id ? { ...r, ...updates } : r));
      return { repositories };
    }),
  removeRepository: (id) =>
    set((state) => ({
      repositories: state.repositories.filter((r) => r.id !== id),
      activeRepositoryId: state.activeRepositoryId === id ? null : state.activeRepositoryId,
    })),

  analysisRunning: false,
  currentAnalysisId: null,
  startAnalysis: (repoId) =>
    set({
      analysisRunning: true,
      currentAnalysisId: repoId,
    }),
  advanceAnalysisStage: (repoId, stage, progress) => {
    const state = get();
    state.updateRepository(repoId, { analysisStage: stage, analysisProgress: progress });
  },
  completeAnalysis: (repoId, updates) => {
    const state = get();
    const repo = state.repositories.find((r) => r.id === repoId);
    if (!repo) return;

    state.updateRepository(repoId, {
      status: 'completed',
      analysisStage: 'completed',
      analysisProgress: 100,
      analysedAt: new Date().toISOString(),
      ...updates,
    });

    const updatedRepo = get().repositories.find((r) => r.id === repoId)!;
    set({
      analysisRunning: false,
      currentAnalysisId: null,
      activeRepositoryId: updatedRepo.id,
    });

    state.addNotification({
      title: 'Analysis Complete',
      message: `${repo.name} has been analysed successfully.`,
      type: 'success',
    });
  },
  failAnalysis: (repoId, error) => {
    const state = get();
    state.updateRepository(repoId, {
      status: 'error',
      analysisStage: null,
      analysisProgress: 0,
      errorMessage: error,
    });
    set({ analysisRunning: false, currentAnalysisId: null });
    state.addNotification({
      title: 'Analysis Failed',
      message: error,
      type: 'error',
    });
  },
  cancelAnalysis: () => {
    const state = get();
    if (state.currentAnalysisId) {
      state.removeRepository(state.currentAnalysisId);
    }
    set({ analysisRunning: false, currentAnalysisId: null });
  },

  notifications: [],
  addNotification: (notification) =>
    set((state) => ({
      notifications: [
        {
          ...notification,
          id: crypto.randomUUID(),
          createdAt: new Date().toISOString(),
          read: false,
        },
        ...state.notifications,
      ],
    })),
  markNotificationRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
    })),
  clearNotifications: () => set({ notifications: [] }),

  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),
  searchOpen: false,
  setSearchOpen: (open) => set({ searchOpen: open }),
}));
