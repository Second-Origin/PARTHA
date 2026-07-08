import { useEffect, useMemo, useState } from 'react';
import { File, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { FileTreeNode } from '@/types';
import { useExplorerStore } from '../store';
import { useResizable } from '../useResizable';
import { deriveFileDetails } from '../fileUtils';
import { FileTreeView } from './FileTreeView';
import { ExplorerToolbar } from './ExplorerToolbar';
import { FileDetailsPanel } from './FileDetailsPanel';
import { CodePreview } from './CodePreview';
import { Breadcrumbs } from './Breadcrumbs';

interface RepositoryExplorerProps {
  fileTree: FileTreeNode[];
}

export function RepositoryExplorer({ fileTree }: RepositoryExplorerProps) {
  const {
    selectedNode, detailsTab, setDetailsTab, expandedFolders, expandFolder,
  } = useExplorerStore();

  const { width: explorerWidth, onMouseDown } = useResizable({
    initialWidth: 280,
    minWidth: 200,
    maxWidth: 420,
    direction: 'left',
  });

  const [collapsed, setCollapsed] = useState(false);
  const rootFolders = useMemo(() => fileTree.filter((node) => node.type === 'folder'), [fileTree]);

  useEffect(() => {
    if (expandedFolders.size === 0 && rootFolders.length > 0) {
      rootFolders.forEach((node) => expandFolder(node.id));
    }
  }, [expandedFolders.size, expandFolder, rootFolders]);

  const fileDetails = useMemo(() => {
    if (!selectedNode || selectedNode.type === 'folder') return null;
    return deriveFileDetails(selectedNode, fileTree);
  }, [selectedNode, fileTree]);

  return (
    <div className="flex h-[calc(100vh-14rem)] rounded-xl border border-border bg-card overflow-hidden">
      {!collapsed && (
        <div className="flex flex-col border-r border-border" style={{ width: explorerWidth }}>
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="text-xs font-medium text-foreground">Explorer</span>
            <button
              onClick={() => setCollapsed(true)}
              className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              <PanelLeftClose className="h-3.5 w-3.5" />
            </button>
          </div>
          <ExplorerToolbar fileTree={fileTree} />
          <FileTreeView fileTree={fileTree} />
        </div>
      )}

      {!collapsed && (
        <div
          className="w-1 cursor-col-resize hover:bg-primary/20 active:bg-primary/30 transition-colors shrink-0"
          onMouseDown={onMouseDown}
        />
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center gap-3 px-4 py-2 border-b border-border">
          {collapsed && (
            <button
              onClick={() => setCollapsed(false)}
              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              <PanelLeftOpen className="h-3.5 w-3.5" />
            </button>
          )}
          {selectedNode ? (
            <Breadcrumbs path={selectedNode.path} />
          ) : (
            <span className="text-xs text-muted-foreground">Select a file to view</span>
          )}
          {selectedNode && selectedNode.type === 'file' && (
            <div className="ml-auto flex items-center gap-1">
              <TabBtn active={detailsTab === 'preview'} onClick={() => setDetailsTab('preview')}>
                Preview
              </TabBtn>
              <TabBtn active={detailsTab === 'details'} onClick={() => setDetailsTab('details')}>
                Details
              </TabBtn>
            </div>
          )}
        </div>

        <div className="flex-1 min-h-0">
          {!selectedNode ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <File className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-sm text-muted-foreground">Select a file from the explorer</p>
              <p className="text-xs text-muted-foreground/70 mt-1">Use arrow keys to navigate, Enter to select</p>
            </div>
          ) : selectedNode.type === 'folder' ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <File className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-sm text-muted-foreground">Folder: {selectedNode.name}</p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                {selectedNode.children?.length || 0} items
              </p>
            </div>
          ) : detailsTab === 'preview' ? (
            <CodePreview node={selectedNode} />
          ) : fileDetails ? (
            <FileDetailsPanel details={fileDetails} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-2.5 py-1 rounded text-xs font-medium transition-colors',
        active ? 'bg-accent text-foreground' : 'text-muted-foreground hover:text-foreground'
      )}
    >
      {children}
    </button>
  );
}
