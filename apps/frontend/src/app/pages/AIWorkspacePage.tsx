import { useNavigate } from 'react-router-dom';
import { Bot, Send, AlertCircle } from 'lucide-react';
import { PageHeader } from '@/shared/components/ui/PageHeader';
import { PreviewBanner } from '@/shared/components/ui/PreviewBanner';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { DataSourceBadge } from '@/shared/components/ui/DataSourceBadge';
import { useAIWorkspace } from '@/features/ai/hooks/useAIWorkspace';
import { cn } from '@/shared/utils/cn';

// Kept identical to the `limitation` recorded for this surface in the
// product-surface registry, which is what classifies it as Preview.
const AI_WORKSPACE_LIMITATION =
  'Evidence-backed answers currently cover authentication and are derived only from the sealed snapshot for the selected revision. Free-form questions need a configured AI provider and use the legacy repository context.';

export function AIWorkspacePage() {
  const navigate = useNavigate();
  const aiWorkspace = useAIWorkspace();
  const activeRepository = aiWorkspace.activeRepository;
  const canSend = Boolean(aiWorkspace.query.trim()) && !aiWorkspace.loading;

  if (aiWorkspace.emptyReason === 'no-completed-repositories') {
    return (
      <div>
        <PageHeader title="AI Workspace" description="Ask questions about your codebase using AI" />
        <PreviewBanner limitation={AI_WORKSPACE_LIMITATION} />
        <EmptyState
          icon={Bot}
          title="No analysed repositories"
          description="Upload and analyse a repository first. AI-powered explanations require a completed analysis pipeline."
          action={{ label: 'Upload Repository', onClick: () => navigate('/upload') }}
        />
      </div>
    );
  }

  if (aiWorkspace.emptyReason === 'no-active-repository' || !activeRepository) {
    return (
      <div>
        <PageHeader title="AI Workspace" description="Ask questions about your codebase using AI" />
        <PreviewBanner limitation={AI_WORKSPACE_LIMITATION} />
        <EmptyState
          icon={Bot}
          title="Select a repository"
          description="Choose an analysed repository from the top bar to start asking questions."
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <PageHeader title="AI Workspace" description={`AI-powered exploration of ${activeRepository.name}`}>
        <DataSourceBadge source={aiWorkspace.source} />
      </PageHeader>
      <PreviewBanner limitation={AI_WORKSPACE_LIMITATION} />

      <div className="flex-1 flex flex-col rounded-xl border border-border bg-card overflow-hidden">
        <div className="flex-1 overflow-y-auto p-5 space-y-4 scrollbar-thin">
          {aiWorkspace.messages.length === 0 ? (
            <div className="flex h-full items-center justify-center text-center">
              <div className="max-w-sm">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted mx-auto mb-4">
                  <Bot className="h-6 w-6 text-muted-foreground" />
                </div>
                <p className="text-sm font-medium text-foreground mb-1">Ask about {activeRepository.name}</p>
                <p className="text-xs text-muted-foreground">
                  Questions are sent to your configured AI provider with repository context and file citations when available.
                </p>
              </div>
            </div>
          ) : (
            aiWorkspace.messages.map((message, index) => (
              <div key={`${message.timestamp}-${index}`} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div className={cn('max-w-[78%] rounded-xl px-4 py-3 text-sm', message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground')}>
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
          {aiWorkspace.error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-3">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <p className="text-sm text-destructive">{aiWorkspace.error}</p>
            </div>
          )}
          {aiWorkspace.suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {aiWorkspace.suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => aiWorkspace.setQuery(suggestion)} className="rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="border-t border-border p-4">
          <form
            className="flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void aiWorkspace.ask();
            }}
          >
            <input
              type="text"
              placeholder="Ask about the codebase..."
              value={aiWorkspace.query}
              onChange={(e) => aiWorkspace.setQuery(e.target.value)}
              className="flex-1 rounded-md border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <button
              disabled={!canSend}
              className={cn(
                'flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground transition-colors',
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
