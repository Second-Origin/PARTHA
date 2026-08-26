import { create } from 'zustand';
import type { EngineeringReview, ReviewCategory, ReviewSeverity, ReviewFinding, ReviewPagination } from '@/shared/types/review';

/** How many findings the backend returns per page. A review can carry 10k+
 * findings (#336) -- both the response payload and the rendered DOM stay
 * bounded to this size regardless of total count. Kept in sync with the
 * route's default `limit` (`apps/backend/app/api/routes/analysis.py`). */
export const FINDINGS_PAGE_SIZE = 50;

interface ReviewState {
  review: EngineeringReview | null;
  /** Replaces the review wholesale: first load, or a fresh page-1 fetch
   * after a filter change. */
  setReview: (review: EngineeringReview | null) => void;
  /** Appends the next fetched page's findings to what's already loaded. */
  appendFindings: (findings: ReviewFinding[], pagination: ReviewPagination) => void;

  selectedFindingId: string | null;
  setSelectedFindingId: (id: string | null) => void;

  filterCategory: ReviewCategory | 'all';
  setFilterCategory: (category: ReviewCategory | 'all') => void;

  filterSeverity: ReviewSeverity | 'all';
  setFilterSeverity: (severity: ReviewSeverity | 'all') => void;

  filterDiagnosticCode: string | null;
  setFilterDiagnosticCode: (code: string | null) => void;

  resetForRepository: () => void;
}

export const useReviewStore = create<ReviewState>((set) => ({
  review: null,
  setReview: (review) => set({ review }),
  appendFindings: (findings, pagination) =>
    set((state) => {
      if (!state.review) return state;
      return {
        review: {
          ...state.review,
          findings: [...state.review.findings, ...findings],
          pagination,
        },
      };
    }),

  selectedFindingId: null,
  setSelectedFindingId: (id) => set({ selectedFindingId: id }),

  filterCategory: 'all',
  setFilterCategory: (category) => set({ filterCategory: category }),

  filterSeverity: 'all',
  setFilterSeverity: (severity) => set({ filterSeverity: severity }),

  filterDiagnosticCode: null,
  setFilterDiagnosticCode: (code) => set({ filterDiagnosticCode: code }),

  resetForRepository: () =>
    set({
      review: null,
      selectedFindingId: null,
      filterCategory: 'all',
      filterSeverity: 'all',
      filterDiagnosticCode: null,
    }),
}));
