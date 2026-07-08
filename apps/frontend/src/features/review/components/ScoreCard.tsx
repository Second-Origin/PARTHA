import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { ReviewScore } from '@/shared/types/review';

interface ScoreCardProps {
  score: ReviewScore;
  onClick?: () => void;
}

export function ScoreCard({ score, onClick }: ScoreCardProps) {
  const TrendIcon = score.trend === 'improving' ? TrendingUp : score.trend === 'declining' ? TrendingDown : Minus;
  const trendColor = score.trend === 'improving' ? 'text-green-400' : score.trend === 'declining' ? 'text-red-400' : 'text-muted-foreground';

  return (
    <button
      onClick={onClick}
      className="rounded-xl border border-border bg-card p-4 text-left hover:border-primary/30 transition-all group"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider capitalize">
          {score.category.replace('-', ' ')}
        </span>
        <div className={cn('flex items-center gap-1', trendColor)}>
          <TrendIcon className="h-3 w-3" />
        </div>
      </div>
      <div className="flex items-end justify-between">
        <div>
          <p className={cn(
            'text-2xl font-bold',
            score.score >= 80 ? 'text-green-400' :
            score.score >= 60 ? 'text-amber-400' :
            score.score >= 40 ? 'text-orange-400' : 'text-red-400'
          )}>
            {score.score}
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">/100</p>
        </div>
        <div className="text-right">
          <ScoreMeter score={score.score} />
          {score.findingsCount > 0 && (
            <p className="text-[10px] text-muted-foreground mt-1">
              {score.findingsCount} {score.findingsCount === 1 ? 'finding' : 'findings'}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

function ScoreMeter({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-green-400' : score >= 60 ? 'bg-amber-400' : score >= 40 ? 'bg-orange-400' : 'bg-red-400';

  return (
    <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
      <div
        className={cn('h-full rounded-full transition-all duration-500', color)}
        style={{ width: `${score}%` }}
      />
    </div>
  );
}

interface OverallScoreProps {
  score: number;
  trend: 'improving' | 'stable' | 'declining';
  totalFindings: number;
  criticalCount: number;
  highCount: number;
}

export function OverallScoreRing({ score, trend, totalFindings, criticalCount, highCount }: OverallScoreProps) {
  const circumference = 2 * Math.PI * 44;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? '#4ade80' : score >= 60 ? '#fbbf24' : score >= 40 ? '#fb923c' : '#f87171';

  return (
    <div className="flex items-center gap-6">
      <div className="relative w-28 h-28">
        <svg className="w-28 h-28 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="44" fill="none" stroke="hsl(var(--muted))" strokeWidth="6" />
          <circle
            cx="50" cy="50" r="44" fill="none"
            stroke={color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-foreground">{score}</span>
          <span className="text-[10px] text-muted-foreground">/ 100</span>
        </div>
      </div>
      <div className="space-y-2">
        <div>
          <p className="text-xs text-muted-foreground">Health Status</p>
          <p className={cn(
            'text-sm font-semibold',
            score >= 80 ? 'text-green-400' : score >= 60 ? 'text-amber-400' : score >= 40 ? 'text-orange-400' : 'text-red-400'
          )}>
            {score >= 80 ? 'Healthy' : score >= 60 ? 'Fair' : score >= 40 ? 'Needs Attention' : 'Critical'}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-muted-foreground">{totalFindings} findings</span>
          {criticalCount > 0 && <span className="text-red-400 font-medium">{criticalCount} critical</span>}
          {highCount > 0 && <span className="text-orange-400 font-medium">{highCount} high</span>}
        </div>
        <div className="flex items-center gap-1.5">
          {trend === 'improving' ? <TrendingUp className="h-3 w-3 text-green-400" /> :
           trend === 'declining' ? <TrendingDown className="h-3 w-3 text-red-400" /> :
           <Minus className="h-3 w-3 text-muted-foreground" />}
          <span className="text-[11px] text-muted-foreground capitalize">{trend}</span>
        </div>
      </div>
    </div>
  );
}
