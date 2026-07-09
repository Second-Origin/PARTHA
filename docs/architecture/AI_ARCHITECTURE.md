# AI Architecture Foundation

Issue #24 establishes the backend architecture for PARTHA's AI subsystem without adding new provider features.

## Goals

- Keep Repository Intelligence as the single source of repository understanding.
- Keep providers behind a common abstraction.
- Keep orchestration provider-agnostic.
- Preserve the existing `/ai/*` API contract and behaviour.

## Component Responsibilities

| Component | Responsibility | Must not do |
| --- | --- | --- |
| `AiService` | Route-facing compatibility facade. | Build prompts, read repository intelligence, or call providers directly. |
| `AiOrchestrator` | Coordinate query and provider-test lifecycles. | Contain provider-specific HTTP logic. |
| `AiProviderConfigStore` | Preserve current file-backed provider configuration behaviour. | Redesign secret storage or persistence. |
| `RepositoryContextBuilder` | Transform `RepositoryIntelligence` into provider-safe `RepositoryContext`. | Parse repositories or read dependency manifests. |
| `PromptBuilder` | Transform `RepositoryContext` and user question into `PromptBundle`. | Format provider-specific payloads. |
| `ProviderRegistry` | Register provider implementations by provider id. | Instantiate providers from request data. |
| `ProviderFactory` | Resolve a provider implementation from validated configuration. | Know provider HTTP details. |
| `LegacyProvider` | Preserve the current provider HTTP behaviour behind `AiProvider`. | Improve provider integrations or add new capabilities. |

## Dependency Graph

```text
AI Routes
  -> AiService
    -> AiOrchestrator
      -> AiProviderConfigStore
      -> RepositoryContextBuilder
        -> RepositoryIntelligenceEngine
      -> PromptBuilder
      -> ProviderFactory
        -> ProviderRegistry
          -> LegacyProvider
```

## Request Lifecycle

1. API route receives an existing `AiQueryRequest`.
2. `AiService.query()` delegates to `AiOrchestrator.query()`.
3. The orchestrator loads the repository record.
4. The orchestrator loads the saved provider configuration.
5. `RepositoryContextBuilder` builds a structured `RepositoryContext` from Repository Intelligence.
6. `PromptBuilder` builds a structured `PromptBundle`.
7. `ProviderFactory` resolves the configured provider.
8. The provider returns a normalized `AiProviderResponse`.
9. The orchestrator returns the existing `AiQueryResponse` shape.

## Repository Context Boundary

Providers consume `RepositoryContext` through `PromptBundle`.

Providers must not:

- parse repositories;
- read repository files;
- call `RepositoryIntelligenceEngine` directly;
- rebuild architecture, dependency, documentation, or review facts.

## Provider Extension Point

Future provider issues can replace individual `LegacyProvider` registry entries with provider-specific implementations:

```text
ProviderRegistry
  openai -> OpenAiProvider
  anthropic -> AnthropicProvider
  gemini -> GeminiProvider
  openrouter -> OpenRouterProvider
  ollama -> OllamaProvider
```

No future provider should require changes to `AiOrchestrator`.

## Out of Scope

This foundation intentionally does not implement:

- provider improvements;
- streaming redesign;
- conversation persistence;
- citation rendering changes;
- secret storage redesign;
- rate limiting;
- health checks;
- frontend changes;
- database migrations.
