import { useCallback, useEffect, useRef, useState } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { Copy, Check, FileWarning, Loader2, ShieldAlert, Target } from 'lucide-react';
import type { FileTreeNode } from '@/shared/types';
import { repositoryService } from '@/shared/services/api/repositories';
import { architectureService } from '@/shared/services/api/architecture';
import { getErrorMessage } from '@/shared/services/api';
import { getMonacoLanguage } from '../fileUtils';
import type { ExplorerCitation } from './RepositoryExplorer';

interface CodePreviewProps {
  node: FileTreeNode;
  repositoryId: string;
  /** When set, the exact cited line span is fetched, verified, and highlighted. */
  citation?: ExplorerCitation | null;
}

export function CodePreview({ node, repositoryId, citation }: CodePreviewProps) {
  const [copied, setCopied] = useState(false);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isBinary, setIsBinary] = useState(false);
  const [isImage, setIsImage] = useState(false);
  const [mediaType, setMediaType] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  // Set only once the cited snapshot/revision has actually been verified by
  // the backend -- never optimistically from the (unverified) URL params.
  const [verifiedRevision, setVerifiedRevision] = useState<{ kind: string | null; value: string | null } | null>(
    null,
  );
  const [unavailableReason, setUnavailableReason] = useState<string | null>(null);
  type Editor = Parameters<OnMount>[0];
  type Monaco = Parameters<OnMount>[1];
  const editorRef = useRef<Editor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const decorationsRef = useRef<ReturnType<Editor['createDecorationsCollection']> | null>(null);
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
    setVerifiedRevision(null);
    setUnavailableReason(null);

    if (citation) {
      // Snapshot-and-revision-verified fetch: the backend proves the
      // returned content genuinely belongs to the cited snapshot's exact
      // immutable revision before returning it. It never falls back to
      // `getFile` -- an unprovable citation reports `status: "unavailable"`
      // with no content, rather than silently showing different content
      // under a trusted-looking snapshot badge.
      architectureService
        .getEvidenceSource(
          repositoryId,
          citation.snapshotId,
          citation.factId,
          citation.path,
          citation.startLine,
          citation.endLine,
        )
        .then((source) => {
          if (cancelled) return;
          if (source.status === 'unavailable') {
            setUnavailableReason(source.reason ?? 'Evidence source unavailable for this snapshot revision.');
            return;
          }
          setContent(source.content ?? '');
          setTruncated(source.truncated);
          setVerifiedRevision({ kind: source.revisionKind, value: source.revisionValue });
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
    }

    repositoryService
      .getFile(repositoryId, node.path)
      .then((file) => {
        if (cancelled) return;
        setContent(file.content);
        setIsBinary(file.isBinary);
        setIsImage(file.isImage);
        setMediaType(file.mediaType ?? null);
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
  }, [clearCopyResetTimer, repositoryId, node.path, citation]);

  useEffect(() => clearCopyResetTimer, [clearCopyResetTimer]);

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
  };

  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco || loading) return;
    decorationsRef.current?.clear();
    // Lines are highlighted only once verification has actually succeeded --
    // never while loading, and never for an unavailable/mismatched citation.
    if (!citation || unavailableReason !== null || error !== null) return;
    const { startLine: start, endLine: end } = citation;
    decorationsRef.current = editor.createDecorationsCollection([
      {
        range: new monaco.Range(start, 1, end, 1),
        options: {
          isWholeLine: true,
          className: 'citation-highlight-line',
          linesDecorationsClassName: 'citation-highlight-margin',
        },
      },
    ]);
    editor.revealLineInCenter(start);
  }, [citation, loading, unavailableReason, error, content]);

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

  const showCopy = !loading && !error && !unavailableReason && !isBinary && !isImage;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-card/50">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground">{node.name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{language}</span>
          {truncated && !isImage && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning/10 text-warning">truncated</span>
          )}
          {citation && verifiedRevision && !unavailableReason && !loading && !error && (
            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">
              <Target className="h-3 w-3" />
              Cited lines {citation.startLine}
              {citation.endLine !== citation.startLine ? `-${citation.endLine}` : ''} · snapshot{' '}
              {citation.snapshotId} · revision {verifiedRevision.kind}:{verifiedRevision.value}
            </span>
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
            {citation ? 'Verifying evidence...' : 'Loading file...'}
          </div>
        ) : unavailableReason ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-6">
            <ShieldAlert className="h-8 w-8 text-warning/60" />
            <p className="text-sm text-foreground">Evidence source unavailable for this snapshot revision.</p>
            <p className="text-xs text-muted-foreground max-w-md">{unavailableReason}</p>
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
