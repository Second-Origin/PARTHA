import { X } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useReviewStore } from '../store';
import type { ReviewCategory, ReviewSeverity } from '@/shared/types/review';

const categories: { value: ReviewCategory | 'all'; label: string }[] = [
  { value: 'all', label: 'All categories' },
  { value: 'architecture_boundaries', label: 'Architecture' },
  { value: 'relationship_resolution', label: 'Relationships' },
  { value: 'source_extraction', label: 'Extraction' },
  { value: 'dependency_declarations', label: 'Dependencies' },
  { value: 'security_vulnerability_scanning', label: 'Vulnerability scanning' },
  { value: 'authentication_evidence', label: 'Authentication' },
  { value: 'repository_structure', label: 'Structure' },
  { value: 'analysis_integrity', label: 'Integrity' },
];

const severities: { value: ReviewSeverity | 'all'; label: string }[] = [
  { value: 'all', label: 'All severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
  { value: 'info', label: 'Info' },
];

export function ReviewFilters() {
  const {
    filterCategory,
    setFilterCategory,
    filterSeverity,
    setFilterSeverity,
    filterDiagnosticCode,
    setFilterDiagnosticCode,
  } = useReviewStore();

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="text-xs text-muted-foreground">
        <span className="sr-only">Filter by severity</span>
        <select
          value={filterSeverity}
          onChange={(event) => setFilterSeverity(event.target.value as ReviewSeverity | 'all')}
          className="rounded-md border border-border bg-background px-2.5 py-1.5 text-xs text-foreground"
        >
          {severities.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
      </label>
      <label className="text-xs text-muted-foreground">
        <span className="sr-only">Filter by category</span>
        <select
          value={filterCategory}
          onChange={(event) => setFilterCategory(event.target.value as ReviewCategory | 'all')}
          className="rounded-md border border-border bg-background px-2.5 py-1.5 text-xs text-foreground"
        >
          {categories.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
      </label>
      {filterDiagnosticCode && (
        <button
          type="button"
          onClick={() => setFilterDiagnosticCode(null)}
          className={cn(
            'inline-flex items-center gap-1 rounded-md border border-primary/30 bg-primary/5 px-2 py-1 text-xs text-primary',
          )}
        >
          {filterDiagnosticCode}
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}
