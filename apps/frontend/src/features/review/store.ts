import { create } from 'zustand';
import type { EngineeringReview, ReviewCategory, ReviewSeverity, ReviewFinding } from '@/shared/types/review';

/** How many findings render at once. A review can carry 10k+ findings (#336)
 * -- rendering them all as DOM nodes in one pass is what made the page
 * unresponsive, not the fetch itself. Revealing more in bounded steps keeps
 * the page interactive regardless of total count. */
const FINDINGS_PAGE_SIZE = 50;

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

  visibleCount: number;
  showMoreFindings: () => void;

  filteredFindings: () => ReviewFinding[];
  visibleFindings: () => ReviewFinding[];
  resetForRepository: () => void;
}

export const useReviewStore = create<ReviewState>((set, get) => ({
  review: null,
  setReview: (review) => set({ review }),

  selectedFindingId: null,
  setSelectedFindingId: (id) => set({ selectedFindingId: id }),

  filterCategory: 'all',
  setFilterCategory: (category) => set({ filterCategory: category, visibleCount: FINDINGS_PAGE_SIZE }),

  filterSeverity: 'all',
  setFilterSeverity: (severity) => set({ filterSeverity: severity, visibleCount: FINDINGS_PAGE_SIZE }),

  filterDiagnosticCode: null,
  setFilterDiagnosticCode: (code) => set({ filterDiagnosticCode: code, visibleCount: FINDINGS_PAGE_SIZE }),

  visibleCount: FINDINGS_PAGE_SIZE,
  showMoreFindings: () => set((state) => ({ visibleCount: state.visibleCount + FINDINGS_PAGE_SIZE })),

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

  visibleFindings: () => get().filteredFindings().slice(0, get().visibleCount),

  resetForRepository: () =>
    set({
      review: null,
      selectedFindingId: null,
      filterCategory: 'all',
      filterSeverity: 'all',
      filterDiagnosticCode: null,
      visibleCount: FINDINGS_PAGE_SIZE,
    }),
}));
