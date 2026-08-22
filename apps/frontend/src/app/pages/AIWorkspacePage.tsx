import { useNavigate } from 'react-router-dom';
import { Bot, Send, AlertCircle, Settings } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { PreviewBanner } from '@/shared/components/ui/PreviewBanner';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { useAIWorkspace } from '@/features/ai/hooks/useAIWorkspace';
import { getErrorDetail } from '@/shared/services/api';
import { cn } from '@/shared/utils/cn';

// Kept identical to the `limitation` recorded for this surface in the
// product-surface registry, which is what classifies it as Preview.
const AI_WORKSPACE_LIMITATION =
  'Free-form questions require a configured AI provider. They receive sealed-snapshot structural facts, heuristic roles, and observed paths, but no source-file contents; provider answers therefore have no automatic citations.';

// States what the surface actually does rather than generic "chat" framing:
// answers are grounded in the already-computed sealed snapshot, and no
// source-file contents leave the instance. It must not claim the thread is
// forgotten -- conversation turns are persisted per owner and repository and
// restored on return (#231), and recent turns are replayed as context, so
// promising otherwise would be a false privacy assurance.
const AI_WORKSPACE_SUBTITLE =
  'Answers are grounded in the structural facts your last analysis already computed — no source-file contents are sent. Your thread is saved for this repository and restored when you return.';

export function AIWorkspacePage() {
  const navigate = useNavigate();
  const aiWorkspace = useAIWorkspace();
  const activeRepository = aiWorkspace.activeRepository;
  const canSend = Boolean(aiWorkspace.query.trim()) && !aiWorkspace.loading;

  if (aiWorkspace.emptyReason === 'no-completed-repositories') {
    return (
      <div>
        <PageHeader title="AI Workspace" description={AI_WORKSPACE_SUBTITLE} />
        <PreviewBanner limitation={AI_WORKSPACE_LIMITATION} />
        <EmptyState
          icon={Bot}
          title="No analysed repositories"
          description="Upload and analyse a repository first. Structural facts for this workspace come from a completed analysis pipeline."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (aiWorkspace.emptyReason === 'no-active-repository' || !activeRepository) {
    return (
      <div>
        <PageHeader title="AI Workspace" description={AI_WORKSPACE_SUBTITLE} />
        <PreviewBanner limitation={AI_WORKSPACE_LIMITATION} />
        <EmptyState
          icon={Bot}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to see its computed structural facts."
        />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-[460px] min-w-0 flex-col">
      <PageHeader title="AI Workspace" description={`${activeRepository.name} · ${AI_WORKSPACE_SUBTITLE}`}>
        <DataSourceBadge source={aiWorkspace.source} />
      </PageHeader>
      <PreviewBanner limitation={AI_WORKSPACE_LIMITATION} />

      <div className="partha-surface flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5 scrollbar-thin sm:p-6">
          {aiWorkspace.messages.length === 0 ? (
            <div className="flex h-full items-center justify-center text-center">
              <div className="max-w-sm">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-[#fa4d01]/15 bg-[#dcecf2]">
                  <Bot className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="text-sm font-medium text-foreground mb-1">Structural facts for {activeRepository.name}</p>
                <p className="text-xs text-muted-foreground">
                  Each answer is generated from the sealed structural facts your last analysis already computed for this repository. No source-file contents are sent to the provider. Your conversation is saved for this repository and restored when you come back, and recent turns are sent along as context.
                </p>
              </div>
            </div>
          ) : (
            aiWorkspace.messages.map((message, index) => (
              <div key={`${message.timestamp}-${index}`} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div className={cn('max-w-[78%] rounded-2xl px-4 py-3 text-sm', message.role === 'user' ? 'bg-primary text-primary-foreground shadow-[0_8px_18px_rgba(250,77,1,0.16)]' : 'border border-[#fa4d01]/15 bg-[#fff7f1] text-foreground')}>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.citations && message.citations.length > 0 && (
                    <div className="mt-3 border-t border-border/60 pt-2 space-y-1">
                      {message.citations.map((citation) => (
                        <p key={citation.file} className="text-2xs text-muted-foreground font-mono">{citation.file}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {aiWorkspace.loading && <p className="text-xs text-muted-foreground">AI provider is thinking...</p>}
          {aiWorkspace.error && (() => {
            const detail = getErrorDetail(aiWorkspace.error);
            return (
              <div className="flex items-start gap-2 rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-3">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                <div className="space-y-1">
                  <p className="text-sm text-destructive">{detail.message}</p>
                  {detail.details.length > 0 && (
                    <ul className="list-disc pl-4 text-xs text-destructive/80">
                      {detail.details.map((d, i) => (
                        <li key={i}>{d}</li>
                      ))}
                    </ul>
                  )}
                  {aiWorkspace.historyError && (
                    <button
                      type="button"
                      onClick={aiWorkspace.retryLoad}
                      className="mt-1 rounded-md border border-destructive/40 px-2.5 py-1 text-xs text-destructive hover:bg-destructive/10 transition-colors"
                    >
                      Retry
                    </button>
                  )}
                </div>
              </div>
            );
          })()}
          {aiWorkspace.suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {aiWorkspace.suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => aiWorkspace.setQuery(suggestion)} className="rounded-xl border border-[#fa4d01]/25 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="shrink-0 border-t border-[#fa4d01]/15 bg-card p-3 sm:p-4">
          {aiWorkspace.providerConfigured === false && (
            <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/5 px-4 py-2.5 text-sm text-amber-200">
              <Settings className="h-4 w-4 shrink-0" />
              <span>
                No AI provider is configured. Free-form questions cannot run until you save a provider in{' '}
                <button
                  type="button"
                  onClick={() => navigate('/settings')}
                  className="underline underline-offset-2 hover:text-amber-100"
                >
                  Settings
                </button>
                .
              </span>
            </div>
          )}
          <form
            className="flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void aiWorkspace.ask();
            }}
          >
            <label htmlFor="ai-workspace-query" className="sr-only">Ask about the codebase</label>
            <input
              id="ai-workspace-query"
              type="text"
              placeholder="Ask about the codebase..."
              value={aiWorkspace.query}
              onChange={(e) => aiWorkspace.setQuery(e.target.value)}
              className="partha-input min-w-0 flex-1 px-3 py-2.5 text-sm sm:px-4"
            />
            <button
              disabled={!canSend}
              className={cn(
                'flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-colors',
                !canSend && 'opacity-50 cursor-not-allowed'
              )}
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
          <p className="text-2xs text-muted-foreground mt-2">Configure a real AI provider in Settings before asking questions.</p>
        </div>
      </div>
    </div>
  );
}
