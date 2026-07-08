import { create } from 'zustand';
import type { EngineeringReview, ReviewCategory, ReviewSeverity, ReviewFinding } from '@/types/review';

interface ReviewState {
  review: EngineeringReview | null;
  setReview: (review: EngineeringReview) => void;

  selectedFindingId: string | null;
  setSelectedFindingId: (id: string | null) => void;

  filterCategory: ReviewCategory | 'all';
  setFilterCategory: (category: ReviewCategory | 'all') => void;

  filterSeverity: ReviewSeverity | 'all';
  setFilterSeverity: (severity: ReviewSeverity | 'all') => void;

  filterStatus: 'open' | 'acknowledged' | 'resolved' | 'all';
  setFilterStatus: (status: 'open' | 'acknowledged' | 'resolved' | 'all') => void;

  filteredFindings: () => ReviewFinding[];
}

export const useReviewStore = create<ReviewState>((set, get) => ({
  review: null,
  setReview: (review) => set({ review }),

  selectedFindingId: null,
  setSelectedFindingId: (id) => set({ selectedFindingId: id }),

  filterCategory: 'all',
  setFilterCategory: (category) => set({ filterCategory: category }),

  filterSeverity: 'all',
  setFilterSeverity: (severity) => set({ filterSeverity: severity }),

  filterStatus: 'all',
  setFilterStatus: (status) => set({ filterStatus: status }),

  filteredFindings: () => {
    const state = get();
    if (!state.review) return [];
    let findings = state.review.findings;

    if (state.filterCategory !== 'all') {
      findings = findings.filter((f) => f.category === state.filterCategory);
    }
    if (state.filterSeverity !== 'all') {
      findings = findings.filter((f) => f.severity === state.filterSeverity);
    }
    if (state.filterStatus !== 'all') {
      findings = findings.filter((f) => f.status === state.filterStatus);
    }

    return findings;
  },
}));
