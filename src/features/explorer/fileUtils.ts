import type { FileTreeNode } from '@/types';

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

export function generateSampleCode(node: FileTreeNode): string {
  if (node.type === 'folder') return '';
  const ext = node.extension;
  if (!ext) return `// ${node.name}\n`;
  const baseName = node.name.replace(/\.[^.]+$/, '');

  if (['tsx', 'jsx'].includes(ext)) {
    const cName = baseName.charAt(0).toUpperCase() + baseName.slice(1).replace(/[-_.]/g, '');
    return `import { useState } from 'react';\n\ninterface ${cName}Props {\n  className?: string;\n}\n\nexport function ${cName}({ className }: ${cName}Props) {\n  const [state, setState] = useState(null);\n\n  return (\n    <div className={className}>\n      <h2>${cName}</h2>\n      {/* Component implementation */}\n    </div>\n  );\n}\n`;
  }

  if (['ts', 'js'].includes(ext)) {
    if (baseName.includes('store') || baseName.includes('Store')) {
      return `import { create } from 'zustand';\n\ninterface ${baseName}State {\n  data: unknown[];\n  loading: boolean;\n  fetch: () => Promise<void>;\n}\n\nexport const use${baseName.charAt(0).toUpperCase() + baseName.slice(1)} = create<${baseName}State>((set) => ({\n  data: [],\n  loading: false,\n  fetch: async () => {\n    set({ loading: true });\n    // Implementation\n    set({ loading: false });\n  },\n}));\n`;
    }
    if (baseName.includes('service') || baseName.includes('Service')) {
      return `const BASE_URL = import.meta.env.VITE_API_URL;\n\nexport async function fetchData<T>(endpoint: string): Promise<T> {\n  const response = await fetch(\`\${BASE_URL}/\${endpoint}\`);\n  if (!response.ok) throw new Error(response.statusText);\n  return response.json();\n}\n\nexport async function postData<T>(endpoint: string, body: unknown): Promise<T> {\n  const response = await fetch(\`\${BASE_URL}/\${endpoint}\`, {\n    method: 'POST',\n    headers: { 'Content-Type': 'application/json' },\n    body: JSON.stringify(body),\n  });\n  if (!response.ok) throw new Error(response.statusText);\n  return response.json();\n}\n`;
    }
    if (baseName === 'index') {
      return `export * from './types';\nexport * from './utils';\n`;
    }
    return `export function ${baseName}() {\n  // Implementation\n}\n`;
  }

  if (ext === 'json') {
    if (baseName === 'package') {
      return `{\n  "name": "project",\n  "version": "1.0.0",\n  "private": true,\n  "type": "module",\n  "scripts": {\n    "dev": "vite",\n    "build": "tsc -b && vite build"\n  },\n  "dependencies": {\n    "react": "^18.3.1",\n    "react-dom": "^18.3.1"\n  }\n}\n`;
    }
    if (baseName === 'tsconfig') {
      return `{\n  "compilerOptions": {\n    "target": "ES2020",\n    "module": "ESNext",\n    "strict": true,\n    "jsx": "react-jsx",\n    "moduleResolution": "bundler"\n  },\n  "include": ["src"]\n}\n`;
    }
    return `{\n  "key": "value"\n}\n`;
  }

  if (ext === 'css' || ext === 'scss') {
    return `:root {\n  --primary: #0066ff;\n  --background: #ffffff;\n  --foreground: #111111;\n}\n\n.container {\n  max-width: 1200px;\n  margin: 0 auto;\n  padding: 0 1rem;\n}\n`;
  }

  if (ext === 'md') {
    return `# ${baseName}\n\nProject documentation.\n\n## Getting Started\n\n\`\`\`bash\nnpm install\nnpm run dev\n\`\`\`\n\n## Features\n\n- Feature 1\n- Feature 2\n`;
  }

  if (ext === 'yaml' || ext === 'yml') {
    return `name: CI\non:\n  push:\n    branches: [main]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n      - run: npm ci\n      - run: npm run build\n`;
  }

  return `// ${node.name}\n// Content will be available after backend integration\n`;
}
