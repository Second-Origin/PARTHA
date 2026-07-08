import { useCallback, useEffect, useRef, useState } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { Copy, Check, FileWarning, Loader2 } from 'lucide-react';
import type { FileTreeNode } from '@/shared/types';
import { repositoryService } from '@/shared/services/api/repositories';
import { getErrorMessage } from '@/shared/services/api';
import { getMonacoLanguage } from '../fileUtils';

interface CodePreviewProps {
  node: FileTreeNode;
  repositoryId: string;
}

export function CodePreview({ node, repositoryId }: CodePreviewProps) {
  const [copied, setCopied] = useState(false);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isBinary, setIsBinary] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

  const language = getMonacoLanguage(node.extension);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setIsBinary(false);
    setTruncated(false);

    repositoryService
      .getFile(repositoryId, node.path)
      .then((file) => {
        if (cancelled) return;
        setContent(file.content);
        setIsBinary(file.isBinary);
        setTruncated(file.truncated);
      })
      .catch((caught) => {
        if (cancelled) return;
        setError(getErrorMessage(caught));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [repositoryId, node.path]);

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-card/50">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground">{node.name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{language}</span>
          {truncated && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning/10 text-warning">truncated</span>
          )}
        </div>
        {!isBinary && !error && (
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading file...
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-6">
            <FileWarning className="h-8 w-8 text-muted-foreground/40" />
            <p className="text-sm text-destructive">{error}</p>
          </div>
        ) : isBinary ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-6">
            <FileWarning className="h-8 w-8 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">Binary file — preview not available.</p>
          </div>
        ) : (
          <Editor
            height="100%"
            language={language}
            value={content}
            theme="vs-dark"
            onMount={handleMount}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              padding: { top: 12 },
              renderLineHighlight: 'none',
              overviewRulerLanes: 0,
              hideCursorInOverviewRuler: true,
              scrollbar: {
                vertical: 'auto',
                horizontal: 'auto',
                verticalScrollbarSize: 8,
              },
              guides: {
                indentation: true,
                bracketPairs: true,
              },
              find: {
                addExtraSpaceOnTop: false,
              },
            }}
          />
        )}
      </div>
    </div>
  );
}
