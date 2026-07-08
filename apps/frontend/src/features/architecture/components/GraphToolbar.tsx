import { useState } from 'react';
import {
  Search,
  Download,
  Maximize2,
  Grid3X3,
  Map,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  Minimize2,
  PanelLeftOpen,
  PanelLeftClose,
} from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useArchitectureStore } from '../store';

interface GraphToolbarProps {
  onFitView: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetLayout: () => void;
  onExportPng: () => void;
  onExportSvg: () => void;
  onExportJson: () => void;
  onExportMarkdown: () => void;
  onToggleFullscreen: () => void;
  isFullscreen: boolean;
}

export function GraphToolbar({
  onFitView,
  onZoomIn,
  onZoomOut,
  onResetLayout,
  onExportPng,
  onExportSvg,
  onExportJson,
  onExportMarkdown,
  onToggleFullscreen,
  isFullscreen,
}: GraphToolbarProps) {
  const {
    searchQuery, setSearchQuery, showGrid, setShowGrid,
    showMiniMap, setShowMiniMap, explorerOpen, setExplorerOpen,
  } = useArchitectureStore();

  return (
    <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between gap-3 pointer-events-none">
      <div className="flex items-center gap-2 pointer-events-auto">
        <ToolbarButton
          icon={explorerOpen ? PanelLeftClose : PanelLeftOpen}
          onClick={() => setExplorerOpen(!explorerOpen)}
          title={explorerOpen ? 'Hide Explorer' : 'Show Explorer'}
        />
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search modules, services, routes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-56 rounded-md border border-border bg-card/90 backdrop-blur-sm pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      <div className="flex items-center gap-1 pointer-events-auto">
        <ToolbarButton icon={ZoomIn} onClick={onZoomIn} title="Zoom In" />
        <ToolbarButton icon={ZoomOut} onClick={onZoomOut} title="Zoom Out" />
        <ToolbarButton icon={Maximize2} onClick={onFitView} title="Fit View" />
        <ToolbarButton icon={RotateCcw} onClick={onResetLayout} title="Reset Layout" />

        <div className="w-px h-5 bg-border mx-1" />

        <ToolbarButton
          icon={Grid3X3}
          onClick={() => setShowGrid(!showGrid)}
          title="Toggle Grid"
          active={showGrid}
        />
        <ToolbarButton
          icon={Map}
          onClick={() => setShowMiniMap(!showMiniMap)}
          title="Toggle Mini Map"
          active={showMiniMap}
        />

        <div className="w-px h-5 bg-border mx-1" />

        <ExportDropdown
          onPng={onExportPng}
          onSvg={onExportSvg}
          onJson={onExportJson}
          onMarkdown={onExportMarkdown}
        />

        <ToolbarButton
          icon={isFullscreen ? Minimize2 : Maximize2}
          onClick={onToggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
        />
      </div>
    </div>
  );
}

function ToolbarButton({
  icon: Icon,
  onClick,
  title,
  active,
}: {
  icon: typeof Search;
  onClick: () => void;
  title: string;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        'flex h-7 w-7 items-center justify-center rounded-md border border-border bg-card/90 backdrop-blur-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors',
        active && 'bg-primary/10 text-primary border-primary/30'
      )}
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

function ExportDropdown({
  onPng,
  onSvg,
  onJson,
  onMarkdown,
}: {
  onPng: () => void;
  onSvg: () => void;
  onJson: () => void;
  onMarkdown: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        title="Export"
        className="flex h-7 w-7 items-center justify-center rounded-md border border-border bg-card/90 backdrop-blur-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
      >
        <Download className="h-3.5 w-3.5" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full right-0 mt-1 w-36 rounded-lg border border-border bg-popover shadow-lg z-50 p-1">
            <button
              onClick={() => { onPng(); setOpen(false); }}
              className="w-full px-3 py-1.5 text-xs text-left rounded-md hover:bg-accent transition-colors"
            >
              Export PNG
            </button>
            <button
              onClick={() => { onSvg(); setOpen(false); }}
              className="w-full px-3 py-1.5 text-xs text-left rounded-md hover:bg-accent transition-colors"
            >
              Export SVG
            </button>
            <button
              onClick={() => { onJson(); setOpen(false); }}
              className="w-full px-3 py-1.5 text-xs text-left rounded-md hover:bg-accent transition-colors"
            >
              Export JSON
            </button>
            <button
              onClick={() => { onMarkdown(); setOpen(false); }}
              className="w-full px-3 py-1.5 text-xs text-left rounded-md hover:bg-accent transition-colors"
            >
              Export Markdown
            </button>
            <button
              disabled
              className="w-full px-3 py-1.5 text-xs text-left rounded-md text-muted-foreground cursor-not-allowed"
            >
              Export PDF Coming Soon
            </button>
          </div>
        </>
      )}
    </div>
  );
}
