import { useEffect, useRef } from 'react';
import { EyeOff, Bookmark, Focus, Expand, Copy } from 'lucide-react';
import { useArchitectureStore } from '../store';

export function NodeContextMenu() {
  const {
    contextMenuTarget, contextMenuPosition, closeContextMenu,
    setSelectedNodeId, setIsolatedSubtree, hideNode,
    toggleBookmark, model,
  } = useArchitectureStore();

  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as HTMLElement)) {
        closeContextMenu();
      }
    };
    if (contextMenuTarget) {
      document.addEventListener('mousedown', handler);
      return () => document.removeEventListener('mousedown', handler);
    }
  }, [contextMenuTarget, closeContextMenu]);

  if (!contextMenuTarget || !contextMenuPosition || !model) return null;

  const node = model.nodes.find((n) => n.id === contextMenuTarget);
  if (!node) return null;

  const actions = [
    { icon: Focus, label: 'Focus Node', action: () => { setSelectedNodeId(contextMenuTarget); closeContextMenu(); } },
    { icon: Expand, label: 'Isolate Subtree', action: () => { setIsolatedSubtree(contextMenuTarget); closeContextMenu(); } },
    { icon: Bookmark, label: 'Toggle Bookmark', action: () => { toggleBookmark(contextMenuTarget); closeContextMenu(); } },
    { icon: EyeOff, label: 'Hide Node', action: () => { hideNode(contextMenuTarget); closeContextMenu(); } },
    { icon: Copy, label: 'Copy Name', action: () => { navigator.clipboard.writeText(node.name); closeContextMenu(); } },
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-[100] min-w-[160px] rounded-lg border border-border bg-popover shadow-xl p-1 animate-in fade-in zoom-in-95 duration-100"
      style={{ left: contextMenuPosition.x, top: contextMenuPosition.y }}
    >
      <div className="px-2 py-1.5 border-b border-border mb-1">
        <p className="text-xs font-medium text-foreground truncate">{node.name}</p>
        <p className="text-[10px] text-muted-foreground capitalize">{node.type.replace('-', ' ')}</p>
      </div>
      {actions.map(({ icon: Icon, label, action }) => (
        <button
          key={label}
          onClick={action}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-foreground hover:bg-accent transition-colors"
        >
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          {label}
        </button>
      ))}
    </div>
  );
}
