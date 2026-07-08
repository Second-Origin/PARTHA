# CORE 2 Repository Intelligence Engine Audit

Issue: GitHub Issue #12, CORE 2 — Repository Intelligence Engine
Date: 2026-07-08

## Objective

Transform PARTHA from independent feature analyzers into a backend platform powered by one reusable Repository Intelligence Engine.

The target execution path is:

```text
Repository
-> Repository Parser
-> Repository Intelligence Engine
-> Knowledge Graph
-> Feature Consumers
```

## Audit Table

| Component | Responsibility | Current behaviour before refactor | Problems | Proposed refactor | Status |
| --- | --- | --- | --- | --- | --- |
| `RepositoryParser` | Build file tree and basic metadata. | Walked repository files, detected language/framework/package manager/config/entrypoint. | Correct place for first parse, but downstream features repeated derived analysis. | Keep as parser-only boundary. Intelligence Engine consumes parser output. | Done |
| `ArchitectureAnalyzer` | Build architecture graph. | Walked `record.file_tree`, grouped paths by route/service/model/config heuristics, generated feature-specific edges. | Duplicated traversal and module heuristics. | Consume `RepositoryIntelligence.modules` and discovery data. | Done |
| `DependencyGraphBuilder` | Build dependency graph. | Re-read `package.json`, `requirements.txt`, and `pyproject.toml` directly from disk. | Duplicated dependency discovery and bypassed parser/intelligence model. | Consume `RepositoryIntelligence.dependencies` and graph relationships. | Done |
| `EngineeringReviewBuilder` | Generate review findings. | Walked `record.file_tree`, inspected metadata, and repeated README/license/test/env heuristics. | Duplicated repository facts and file traversal. | Consume `RepositoryIntelligence.discovery`, statistics, and files. | Done |
| `DocumentationService` | Generate docs. | Walked `record.file_tree`, rebuilt architecture, filtered API/env/deploy files independently. | Duplicated traversal and file classification. | Consume discovery, files, API routes, and architecture from intelligence-backed consumers. | Done |
| `AiService` | Build repository context for AI. | Walked file tree and used shallow metadata only. | AI did not consume reusable intelligence or graph context. | Consume Repository Intelligence modules, dependencies, files, and discovery. | Done |
| `AnalysisService` | Orchestrate analysis. | Called feature consumers, but no durable central intelligence artifact existed. | Analysis did not guarantee a single source of truth. | Build and persist Repository Intelligence before consumer generation. | Done |
| Repository persistence | Store parsed metadata and file tree. | Stored `repo_metadata` and `file_tree`. | No persisted knowledge graph. | Persist serialized intelligence under `repo_metadata.intelligence` to avoid DB migration. | Done |

## Duplicated Logic Removed

| Duplicate area | Previous locations | New source of truth |
| --- | --- | --- |
| File traversal | Architecture, Review, Documentation, AI | `RepositoryIntelligenceEngine._flatten_files` |
| Dependency manifest reading | Dependency Graph | `RepositoryIntelligenceEngine._dependencies` |
| Module classification | Architecture | `RepositoryIntelligenceEngine._modules` and file roles |
| API route discovery | Documentation heuristics | `SourceFileIntelligence.api_routes` |
| Environment/deploy/config discovery | Documentation and Review | `RepositoryDiscovery` |
| AI context file selection | AI file-tree walker | `RepositoryIntelligence.files`, modules, dependencies |

## New Central Model

The engine produces `RepositoryIntelligence` containing:

- repository metadata;
- discovery facts;
- source file intelligence;
- symbols;
- modules;
- dependencies;
- serializable knowledge graph nodes and relationships.

Relationship types include:

- `contains`
- `imports`
- `depends_on`
- `exports`

The model is intentionally serializable so future workers, AI providers, search indexes, and hosted services can consume the same artifact.

## Consumer Refactor Summary

| Consumer | Refactor result |
| --- | --- |
| Architecture | Builds nodes/layers/modules from `RepositoryIntelligence.modules`. |
| Dependency Graph | Builds dependency nodes and edges from `RepositoryIntelligence.dependencies` and graph relationships. |
| Engineering Review | Uses discovery statistics, environment files, CI files, README/license facts. |
| Documentation | Uses discovery, API routes, env/deployment files, and intelligence-backed architecture. |
| AI Workspace | Uses modules, dependencies, discovery, selected files, and file list from intelligence. |
| Repository Explorer | Continues to use parsed file tree from repository record. Future enhancement can consume file intelligence directly. |
| Insights | Not implemented yet; should consume `RepositoryIntelligence` when added. |

## Remaining Work

| Area | Reason |
| --- | --- |
| Local import resolution | The graph records imports, but local import-to-file resolution is still shallow. |
| Call graph extraction | Symbol extraction exists, but call relationships are not yet deeply parsed. |
| Inheritance/composition | Regex/Tree-sitter integration can be expanded for language-specific relationships. |
| Database column | Intelligence is persisted inside `repo_metadata.intelligence` to avoid migration risk. A dedicated JSON column can be added later. |
| Repository Explorer | Explorer still reads `file_tree`; it does not yet expose richer file intelligence in the UI. |
| Insights | The Insights backend consumer remains future work. |

## Verification

Tests added in `apps/backend/tests/test_repository_intelligence.py` cover:

- language detection;
- framework detection;
- package manager/build system detection;
- module detection;
- API route extraction;
- symbol extraction;
- dependency extraction;
- knowledge graph relationships;
- serialization/persistence;
- architecture, dependency, and review consumers.
