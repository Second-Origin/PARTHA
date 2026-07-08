import { cn } from '@/utils/cn';
import { useReviewStore } from '../store';
import type { ReviewCategory, ReviewSeverity } from '@/types/review';

const categories: { value: ReviewCategory | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'architecture', label: 'Architecture' },
  { value: 'security', label: 'Security' },
  { value: 'performance', label: 'Performance' },
  { value: 'maintainability', label: 'Maintainability' },
  { value: 'scalability', label: 'Scalability' },
  { value: 'code-quality', label: 'Code Quality' },
  { value: 'documentation', label: 'Documentation' },
  { value: 'testing', label: 'Testing' },
  { value: 'dependency-health', label: 'Dependencies' },
  { value: 'configuration', label: 'Configuration' },
];

const severities: { value: ReviewSeverity | 'all'; label: string; color: string }[] = [
  { value: 'all', label: 'All', color: '' },
  { value: 'critical', label: 'Critical', color: 'text-red-400' },
  { value: 'high', label: 'High', color: 'text-orange-400' },
  { value: 'medium', label: 'Medium', color: 'text-amber-400' },
  { value: 'low', label: 'Low', color: 'text-blue-400' },
];

export function ReviewFilters() {
  const { filterCategory, setFilterCategory, filterSeverity, setFilterSeverity } = useReviewStore();

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
      <div className="flex items-center gap-1 overflow-x-auto scrollbar-thin pb-1">
        {severities.map(({ value, label, color }) => (
          <button
            key={value}
            onClick={() => setFilterSeverity(value)}
            className={cn(
              'px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap transition-colors',
              filterSeverity === value
                ? 'bg-accent text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
            )}
          >
            <span className={cn(filterSeverity === value && color)}>{label}</span>
          </button>
        ))}
      </div>
      <div className="w-px h-5 bg-border hidden sm:block" />
      <div className="flex items-center gap-1 overflow-x-auto scrollbar-thin pb-1">
        {categories.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setFilterCategory(value)}
            className={cn(
              'px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap transition-colors',
              filterCategory === value
                ? 'bg-accent text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
