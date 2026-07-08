import { useState } from 'react';
import { Download } from 'lucide-react';
import type { EngineeringReview } from '@/types/review';

interface ReviewExportProps {
  review: EngineeringReview;
}

export function ReviewExport({ review }: ReviewExportProps) {
  const [open, setOpen] = useState(false);

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(review, null, 2)], { type: 'application/json' });
    download(blob, `${review.repositoryName}-review.json`);
    setOpen(false);
  };

  const exportMarkdown = () => {
    const md = generateMarkdown(review);
    const blob = new Blob([md], { type: 'text/markdown' });
    download(blob, `${review.repositoryName}-review.md`);
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border text-xs font-medium text-foreground hover:bg-accent transition-colors"
      >
        <Download className="h-3.5 w-3.5" />
        Export
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full right-0 mt-1 w-40 rounded-lg border border-border bg-popover shadow-lg z-50 p-1">
            <button
              onClick={exportMarkdown}
              className="w-full px-3 py-1.5 text-xs text-left rounded-md hover:bg-accent transition-colors"
            >
              Markdown
            </button>
            <button
              onClick={exportJson}
              className="w-full px-3 py-1.5 text-xs text-left rounded-md hover:bg-accent transition-colors"
            >
              JSON
            </button>
            <button
              disabled
              className="w-full px-3 py-1.5 text-xs text-left rounded-md text-muted-foreground cursor-not-allowed"
            >
              PDF Coming Soon
            </button>
            <button
              disabled
              className="w-full px-3 py-1.5 text-xs text-left rounded-md text-muted-foreground cursor-not-allowed"
            >
              Share Coming Soon
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function generateMarkdown(review: EngineeringReview): string {
  const lines: string[] = [
    `# Engineering Review: ${review.repositoryName}`,
    '',
    `**Generated:** ${new Date(review.generatedAt).toLocaleString()}`,
    '',
    '## Executive Summary',
    '',
    `| Metric | Value |`,
    `| --- | --- |`,
    `| Overall Score | ${review.summary.overallScore}/100 |`,
    `| Total Findings | ${review.summary.totalFindings} |`,
    `| Critical | ${review.summary.criticalCount} |`,
    `| High | ${review.summary.highCount} |`,
    `| Medium | ${review.summary.mediumCount} |`,
    `| Low | ${review.summary.lowCount} |`,
    '',
    '## Health Scores',
    '',
    '| Category | Score | Risk | Findings |',
    '| --- | --- | --- | --- |',
  ];

  for (const score of review.scores) {
    lines.push(`| ${score.category.replace('-', ' ')} | ${score.score}/100 | ${score.riskLevel} | ${score.findingsCount} |`);
  }

  lines.push('', '## Findings', '');

  for (const finding of review.findings) {
    lines.push(`### ${finding.severity.toUpperCase()}: ${finding.title}`);
    lines.push('');
    lines.push(`**Category:** ${finding.category.replace('-', ' ')}`);
    lines.push(`**Effort:** ${finding.estimatedEffort}`);
    lines.push('');
    lines.push(`**Problem:** ${finding.problem}`);
    lines.push('');
    lines.push(`**Impact:** ${finding.impact}`);
    lines.push('');
    lines.push(`**Recommendation:** ${finding.recommendation}`);
    lines.push('');
    if (finding.affectedFiles.length > 0) {
      lines.push(`**Affected Files:** ${finding.affectedFiles.join(', ')}`);
      lines.push('');
    }
  }

  if (review.roadmap.length > 0) {
    lines.push('## Improvement Roadmap', '');
    for (const step of review.roadmap) {
      lines.push(`${review.roadmap.indexOf(step) + 1}. **${step.title}** (${step.estimatedEffort})`);
      lines.push(`   ${step.description}`);
      lines.push('');
    }
  }

  return lines.join('\n');
}
