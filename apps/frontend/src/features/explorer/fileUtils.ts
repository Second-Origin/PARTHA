import type { FileTreeNode } from '@/shared/types';

export interface ExplorerCitation {
  path: string;
  startLine: number;
  endLine: number;
  snapshotId: string;
  factId: string;
}

function parsePositiveInteger(value: string | null): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 ? parsed : null;
}

/**
 * Parse an evidence-citation deep-link's query params defensively: any
 * missing or malformed field (non-integer line, end before start, empty
 * path/snapshot/fact id) yields `null` rather than a partially valid citation
 * that could produce an invalid Monaco range or an unverified request.
 */
export function parseEvidenceCitation(searchParams: URLSearchParams): ExplorerCitation | null {
  const path = searchParams.get('path');
  const snapshotId = searchParams.get('snapshotId');
  const factId = searchParams.get('factId');
  const startLine = parsePositiveInteger(searchParams.get('startLine'));
  const endLine = parsePositiveInteger(searchParams.get('endLine'));

  if (!path || !snapshotId || !factId || startLine === null || endLine === null || endLine < startLine) {
    return null;
  }
  return { path, startLine, endLine, snapshotId, factId };
}

export interface FileDetails {
  name: string;
  path: string;
  extension: string | null;
  language: string | null;
  estimatedSize: number;
  imports: string[];
  exports: string[];
  relatedModules: string[];
  dependencies: string[];
}

export function deriveFileDetails(node: FileTreeNode, allNodes: FileTreeNode[]): FileDetails {
  const ext = node.extension || null;
  const lang = node.language || inferLanguage(ext);

  return {
    name: node.name,
    path: node.path,
    extension: ext,
    language: lang,
    estimatedSize: node.size || 0,
    imports: inferImports(node, allNodes),
    exports: inferExports(node),
    relatedModules: inferRelatedModules(node),
    dependencies: inferDependencies(node),
  };
}

function inferLanguage(ext: string | null): string | null {
  if (!ext) return null;
  const map: Record<string, string> = {
    ts: 'TypeScript', tsx: 'TypeScript (React)', js: 'JavaScript', jsx: 'JavaScript (React)',
    py: 'Python', rb: 'Ruby', go: 'Go', rs: 'Rust', java: 'Java',
    kt: 'Kotlin', swift: 'Swift', cs: 'C#', cpp: 'C++', c: 'C',
    html: 'HTML', css: 'CSS', scss: 'SCSS', json: 'JSON', yaml: 'YAML',
    yml: 'YAML', md: 'Markdown', sql: 'SQL', sh: 'Shell', toml: 'TOML',
    xml: 'XML', svg: 'SVG', graphql: 'GraphQL', prisma: 'Prisma',
  };
  return map[ext] || null;
}

function inferImports(node: FileTreeNode, allNodes: FileTreeNode[]): string[] {
  if (!node.extension) return [];
  const codeExtensions = ['ts', 'tsx', 'js', 'jsx', 'py', 'go', 'rs', 'java'];
  if (!codeExtensions.includes(node.extension)) return [];

  const parentDir = node.path.substring(0, node.path.lastIndexOf('/'));
  const siblings = flattenTree(allNodes).filter(
    (n) => n.type === 'file' && n.path !== node.path && n.path.startsWith(parentDir)
  );

  return siblings
    .slice(0, 4)
    .map((s) => `./${s.name.replace(/\.[^.]+$/, '')}`)
    .concat(inferPackageImports(node));
}

function inferPackageImports(node: FileTreeNode): string[] {
  if (!node.extension) return [];
  const ext = node.extension;
  if (['ts', 'tsx', 'js', 'jsx'].includes(ext)) {
    const name = node.name.toLowerCase();
    const pkgs: string[] = [];
    if (name.includes('component') || ext === 'tsx' || ext === 'jsx') pkgs.push('react');
    if (name.includes('store')) pkgs.push('zustand');
    if (name.includes('api') || name.includes('service')) pkgs.push('fetch');
    if (name.includes('test')) pkgs.push('vitest');
    return pkgs;
  }
  return [];
}

function inferExports(node: FileTreeNode): string[] {
  if (!node.extension) return [];
  const codeExtensions = ['ts', 'tsx', 'js', 'jsx'];
  if (!codeExtensions.includes(node.extension)) return [];

  const baseName = node.name.replace(/\.[^.]+$/, '');
  const exports: string[] = [];

  if (['tsx', 'jsx'].includes(node.extension)) {
    const componentName = baseName.charAt(0).toUpperCase() + baseName.slice(1);
    exports.push(componentName);
  } else if (node.name === 'index.ts' || node.name === 'index.js') {
    exports.push('* (barrel export)');
  } else {
    const camelName = baseName.replace(/[-.](.)/g, (_, c) => c.toUpperCase());
    exports.push(camelName);
  }

  return exports;
}

function inferRelatedModules(node: FileTreeNode): string[] {
  const parentDir = node.path.substring(0, node.path.lastIndexOf('/'));
  const parts = parentDir.split('/').filter(Boolean);
  return parts.length > 0 ? [parts[parts.length - 1]] : [];
}

function inferDependencies(node: FileTreeNode): string[] {
  if (!node.extension) return [];
  const ext = node.extension;
  if (!['ts', 'tsx', 'js', 'jsx'].includes(ext)) return [];

  const deps: string[] = [];
  const name = node.name.toLowerCase();
  if (name.includes('page') || name.includes('view')) deps.push('router');
  if (name.includes('store')) deps.push('state-management');
  if (name.includes('api') || name.includes('service')) deps.push('network');
  if (['tsx', 'jsx'].includes(ext)) deps.push('ui-framework');
  return deps;
}

export function flattenTree(nodes: FileTreeNode[]): FileTreeNode[] {
  const result: FileTreeNode[] = [];
  function walk(list: FileTreeNode[]) {
    for (const node of list) {
      result.push(node);
      if (node.children) walk(node.children);
    }
  }
  walk(nodes);
  return result;
}

export function getFileIcon(node: FileTreeNode): string {
  if (node.type === 'folder') return 'folder';
  const ext = node.extension;
  if (!ext) return 'file';
  const iconMap: Record<string, string> = {
    ts: 'typescript', tsx: 'react', js: 'javascript', jsx: 'react',
    json: 'json', css: 'css', scss: 'css', html: 'html',
    md: 'markdown', py: 'python', go: 'go', rs: 'rust',
    java: 'java', yaml: 'yaml', yml: 'yaml', toml: 'config',
    sh: 'terminal', sql: 'database', svg: 'image', png: 'image',
    jpg: 'image', gif: 'image', ico: 'image', txt: 'text',
  };
  return iconMap[ext] || 'file';
}

export function getMonacoLanguage(ext: string | null | undefined): string {
  if (!ext) return 'plaintext';
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    json: 'json', css: 'css', scss: 'scss', html: 'html',
    md: 'markdown', py: 'python', go: 'go', rs: 'rust',
    java: 'java', yaml: 'yaml', yml: 'yaml', xml: 'xml',
    sql: 'sql', sh: 'shell', graphql: 'graphql',
  };
  return map[ext] || 'plaintext';
}
