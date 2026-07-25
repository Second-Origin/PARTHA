import { create } from 'zustand';
import type { EngineeringReview, ReviewCategory, ReviewSeverity, ReviewFinding } from '@/shared/types/review';

interface ReviewState {
  review: EngineeringReview | null;
  setReview: (review: EngineeringReview | null) => void;

  selectedFindingId: string | null;
  setSelectedFindingId: (id: string | null) => void;

  filterCategory: ReviewCategory | 'all';
  setFilterCategory: (category: ReviewCategory | 'all') => void;

  filterSeverity: ReviewSeverity | 'all';
  setFilterSeverity: (severity: ReviewSeverity | 'all') => void;

  filterDiagnosticCode: string | null;
  setFilterDiagnosticCode: (code: string | null) => void;

  filteredFindings: () => ReviewFinding[];
  resetForRepository: () => void;
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

  filterDiagnosticCode: null,
  setFilterDiagnosticCode: (code) => set({ filterDiagnosticCode: code }),

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
    if (state.filterDiagnosticCode) {
      findings = findings.filter((f) => f.diagnosticCode === state.filterDiagnosticCode);
    }

    return findings;
  },

  resetForRepository: () =>
    set({
      review: null,
      selectedFindingId: null,
      filterCategory: 'all',
      filterSeverity: 'all',
      filterDiagnosticCode: null,
    }),
}));
