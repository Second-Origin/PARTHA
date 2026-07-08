import { useCallback, useRef } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { Copy, Check } from 'lucide-react';
import { useState } from 'react';
import type { FileTreeNode } from '@/types';
import { getMonacoLanguage, generateSampleCode } from '../fileUtils';

interface CodePreviewProps {
  node: FileTreeNode;
}

export function CodePreview({ node }: CodePreviewProps) {
  const [copied, setCopied] = useState(false);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

  const code = generateSampleCode(node);
  const language = getMonacoLanguage(node.extension);

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-card/50">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground">{node.name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{language}</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="flex-1 min-h-0">
        <Editor
          height="100%"
          language={language}
          value={code}
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
      </div>
    </div>
  );
}
