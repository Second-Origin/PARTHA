import { useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  File,
  Folder,
  FolderOpen,
  FileCode,
  FileJson,
  FileType,
  Image,
  Terminal,
  Database,
  Settings,
  FileText,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import type { FileTreeNode } from '@/shared/types';
import { useExplorerStore } from '../store';
import { flattenTree } from '../fileUtils';

const fileIconMap: Record<string, typeof File> = {
  typescript: FileCode,
  react: FileCode,
  javascript: FileCode,
  json: FileJson,
  css: FileType,
  html: FileType,
  markdown: FileText,
  python: FileCode,
  go: FileCode,
  rust: FileCode,
  java: FileCode,
  yaml: Settings,
  config: Settings,
  terminal: Terminal,
  database: Database,
  image: Image,
  text: FileText,
  file: File,
};

function getIconForFile(node: FileTreeNode): typeof File {
  if (node.type === 'folder') return Folder;
  const ext = node.extension;
  if (!ext) return File;
  const extMap: Record<string, string> = {
    ts: 'typescript', tsx: 'react', js: 'javascript', jsx: 'react',
    json: 'json', css: 'css', scss: 'css', html: 'html',
    md: 'markdown', py: 'python', go: 'go', rs: 'rust',
    java: 'java', yaml: 'yaml', yml: 'yaml', toml: 'config',
    sh: 'terminal', sql: 'database', svg: 'image', png: 'image',
  };
  const iconType = extMap[ext] || 'file';
  return fileIconMap[iconType] || File;
}

function getIconColor(node: FileTreeNode): string {
  if (node.type === 'folder') return '';
  const ext = node.extension;
  if (!ext) return 'text-muted-foreground';
  const colorMap: Record<string, string> = {
    ts: 'text-blue-400', tsx: 'text-blue-400',
    js: 'text-yellow-400', jsx: 'text-yellow-400',
    json: 'text-yellow-600', css: 'text-sky-400', scss: 'text-pink-400',
    html: 'text-orange-400', md: 'text-gray-400', py: 'text-green-400',
    go: 'text-cyan-400', rs: 'text-orange-500', java: 'text-red-400',
    yaml: 'text-rose-400', yml: 'text-rose-400',
    sh: 'text-green-500', sql: 'text-violet-400',
  };
  return colorMap[ext] || 'text-muted-foreground';
}

interface TreeItemProps {
  node: FileTreeNode;
  depth: number;
  searchQuery: string;
}

function TreeItem({ node, depth, searchQuery }: TreeItemProps) {
  const {
    expandedFolders, toggleFolder, selectedFileId, selectFile, focusedId, setFocusedId,
  } = useExplorerStore();

  const isExpanded = expandedFolders.has(node.id);
  const isSelected = selectedFileId === node.id;
  const isFocused = focusedId === node.id;
  const isFolder = node.type === 'folder';
  const Icon = getIconForFile(node);
  const iconColor = getIconColor(node);

  const matchesSearch = useMemo(() => {
    if (!searchQuery) return true;
    return node.name.toLowerCase().includes(searchQuery.toLowerCase());
  }, [searchQuery, node.name]);

  const hasMatchingDescendant = useMemo(() => {
    if (!searchQuery || !node.children) return false;
    function check(nodes: FileTreeNode[]): boolean {
      return nodes.some(
        (n) => n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (n.children && check(n.children))
      );
    }
    return check(node.children);
  }, [searchQuery, node.children]);

  if (searchQuery && !matchesSearch && !hasMatchingDescendant) return null;

  const handleClick = () => {
    setFocusedId(node.id);
    if (isFolder) toggleFolder(node.id);
    else selectFile(node);
  };

  return (
    <div>
      <button
        onClick={handleClick}
        data-node-id={node.id}
        className={cn(
          'w-full flex items-center gap-1.5 py-[3px] px-1.5 rounded text-left text-[13px] transition-colors group',
          isSelected && 'bg-primary/10 text-primary',
          isFocused && !isSelected && 'bg-accent/60',
          !isSelected && !isFocused && 'hover:bg-accent/40'
        )}
        style={{ paddingLeft: `${depth * 14 + 6}px` }}
      >
        {isFolder ? (
          <ChevronRight
            className={cn(
              'h-3 w-3 text-muted-foreground shrink-0 transition-transform duration-100',
              isExpanded && 'rotate-90'
            )}
          />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {isFolder ? (
          isExpanded ? (
            <FolderOpen className="h-4 w-4 text-primary/70 shrink-0" />
          ) : (
            <Folder className="h-4 w-4 text-muted-foreground shrink-0" />
          )
        ) : (
          <Icon className={cn('h-4 w-4 shrink-0', iconColor)} />
        )}
        <span className={cn(
          'truncate',
          searchQuery && matchesSearch && 'font-medium text-foreground'
        )}>
          {node.name}
        </span>
        {node.size != null && node.type === 'file' && (
          <span className="ml-auto text-[10px] text-muted-foreground/60 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            {formatSize(node.size)}
          </span>
        )}
      </button>

      <AnimatePresence>
        {isFolder && isExpanded && node.children && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="overflow-hidden"
          >
            {sortChildren(node.children).map((child) => (
              <TreeItem
                key={child.id}
                node={child}
                depth={depth + 1}
                searchQuery={searchQuery}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function sortChildren(children: FileTreeNode[]): FileTreeNode[] {
  return [...children].sort((a, b) => {
    if (a.type === 'folder' && b.type === 'file') return -1;
    if (a.type === 'file' && b.type === 'folder') return 1;
    return a.name.localeCompare(b.name);
  });
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  return `${(bytes / 1024).toFixed(1)}K`;
}

interface FileTreeViewProps {
  fileTree: FileTreeNode[];
}

export function FileTreeView({ fileTree }: FileTreeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const {
    searchQuery, focusedId, setFocusedId, expandedFolders,
    toggleFolder, selectFile, expandFolder,
  } = useExplorerStore();

  const visibleNodes = useMemo(() => {
    const result: FileTreeNode[] = [];
    function walk(nodes: FileTreeNode[]) {
      for (const node of sortChildren(nodes)) {
        if (searchQuery && !node.name.toLowerCase().includes(searchQuery.toLowerCase())) {
          if (node.children) {
            const hasMatch = flattenTree(node.children).some(
              (n) => n.name.toLowerCase().includes(searchQuery.toLowerCase())
            );
            if (!hasMatch) continue;
          } else continue;
        }
        result.push(node);
        if (node.type === 'folder' && expandedFolders.has(node.id) && node.children) {
          walk(node.children);
        }
      }
    }
    walk(fileTree);
    return result;
  }, [fileTree, expandedFolders, searchQuery]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!focusedId) {
      if (visibleNodes.length > 0) setFocusedId(visibleNodes[0].id);
      return;
    }

    const idx = visibleNodes.findIndex((n) => n.id === focusedId);
    if (idx === -1) return;
    const current = visibleNodes[idx];

    switch (e.key) {
      case 'ArrowDown': {
        e.preventDefault();
        if (idx < visibleNodes.length - 1) {
          setFocusedId(visibleNodes[idx + 1].id);
          scrollToNode(visibleNodes[idx + 1].id);
        }
        break;
      }
      case 'ArrowUp': {
        e.preventDefault();
        if (idx > 0) {
          setFocusedId(visibleNodes[idx - 1].id);
          scrollToNode(visibleNodes[idx - 1].id);
        }
        break;
      }
      case 'ArrowRight': {
        e.preventDefault();
        if (current.type === 'folder') {
          if (!expandedFolders.has(current.id)) expandFolder(current.id);
          else if (current.children && current.children.length > 0) {
            const firstChild = sortChildren(current.children)[0];
            setFocusedId(firstChild.id);
          }
        }
        break;
      }
      case 'ArrowLeft': {
        e.preventDefault();
        if (current.type === 'folder' && expandedFolders.has(current.id)) {
          toggleFolder(current.id);
        }
        break;
      }
      case 'Enter':
      case ' ': {
        e.preventDefault();
        if (current.type === 'folder') toggleFolder(current.id);
        else selectFile(current);
        break;
      }
    }
  }, [focusedId, visibleNodes, expandedFolders, setFocusedId, expandFolder, toggleFolder, selectFile]);

  function scrollToNode(id: string) {
    const el = containerRef.current?.querySelector(`[data-node-id="${id}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto scrollbar-thin p-1 outline-none"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {fileTree.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
          No files
        </div>
      ) : (
        sortChildren(fileTree).map((node) => (
          <TreeItem key={node.id} node={node} depth={0} searchQuery={searchQuery} />
        ))
      )}
    </div>
  );
}
