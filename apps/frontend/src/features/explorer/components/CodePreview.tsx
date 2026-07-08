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
  const [isImage, setIsImage] = useState(false);
  const [mediaType, setMediaType] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const copyResetTimerRef = useRef<number | null>(null);

  const language = getMonacoLanguage(node.extension);

  const clearCopyResetTimer = useCallback(() => {
    if (copyResetTimerRef.current !== null) {
      window.clearTimeout(copyResetTimerRef.current);
      copyResetTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    clearCopyResetTimer();
    setLoading(true);
    setContent('');
    setCopied(false);
    setCopyError(null);
    setError(null);
    setIsBinary(false);
    setIsImage(false);
    setMediaType(null);
    setTruncated(false);

    repositoryService
      .getFile(repositoryId, node.path)
      .then((file) => {
        if (cancelled) return;
        setContent(file.content);
        setIsBinary(file.isBinary);
        setIsImage(file.isImage);
        setMediaType(file.mediaType);
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
  }, [clearCopyResetTimer, repositoryId, node.path]);

  useEffect(() => clearCopyResetTimer, [clearCopyResetTimer]);

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  const handleCopy = useCallback(async () => {
    clearCopyResetTimer();
    setCopyError(null);

    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      copyResetTimerRef.current = window.setTimeout(() => {
        setCopied(false);
        copyResetTimerRef.current = null;
      }, 2000);
    } catch {
      setCopied(false);
      setCopyError('Copy failed');
    }
  }, [clearCopyResetTimer, content]);

  const showCopy = !loading && !error && !isBinary && !isImage;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-card/50">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground">{node.name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{language}</span>
          {truncated && !isImage && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning/10 text-warning">truncated</span>
          )}
        </div>
        {showCopy && (
          <div className="flex items-center gap-2">
            {copyError && <span className="text-[10px] text-destructive">{copyError}</span>}
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
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
        ) : isImage ? (
          truncated || !content ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-6">
              <FileWarning className="h-8 w-8 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">Image is too large to preview.</p>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full p-4 overflow-auto bg-muted/30">
              <img
                src={`data:${mediaType ?? 'image/png'};base64,${content}`}
                alt={node.name}
                className="max-h-full max-w-full object-contain"
              />
            </div>
          )
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
