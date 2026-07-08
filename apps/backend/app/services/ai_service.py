from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationServiceError
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.ai import (
    AiCitation,
    AiMessage,
    AiProviderConfig,
    AiProviderPublicConfig,
    AiProviderTestRequest,
    AiProviderTestResponse,
    AiQueryRequest,
    AiQueryResponse,
)

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
}


class AiService:
    def __init__(
        self,
        repository: RepositoryRepository,
        settings: Settings,
        intelligence: RepositoryIntelligenceEngine | None = None,
    ) -> None:
        self.repository = repository
        self.path = settings.storage_path / "ai-provider.json"
        self.intelligence = intelligence or RepositoryIntelligenceEngine()

    def get_config(self) -> AiProviderPublicConfig:
        config = self._read_config()
        if not config:
            return AiProviderPublicConfig()
        return AiProviderPublicConfig(
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            has_api_key=bool(config.api_key),
        )

    def save_config(self, config: AiProviderConfig) -> AiProviderPublicConfig:
        if config.provider != "ollama" and not config.api_key:
            previous = self._read_config()
            if previous and previous.provider == config.provider and previous.api_key:
                config.api_key = previous.api_key
            else:
                raise ValidationServiceError("API key is required for this provider.")

        config.model = config.model or DEFAULT_MODELS[config.provider]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(config.model_dump_json(), encoding="utf-8")
        os.chmod(self.path, 0o600)
        return self.get_config()

    async def test_connection(self, request: AiProviderTestRequest) -> AiProviderTestResponse:
        saved = self._read_config()
        provider = request.provider or saved.provider if saved else request.provider
        if not provider:
            raise ValidationServiceError("Choose an AI provider before testing.")
        config = AiProviderConfig(
            provider=provider,
            api_key=request.api_key or (saved.api_key if saved and saved.provider == provider else None),
            model=request.model or (saved.model if saved and saved.provider == provider else None) or DEFAULT_MODELS[provider],
            base_url=request.base_url or (saved.base_url if saved and saved.provider == provider else None),
        )
        await self._call_provider(config, "Reply with the single word: ok", "Connection test.")
        return AiProviderTestResponse(ok=True, message=f"{provider} connection succeeded.", checked_at=datetime.now(UTC))

    async def query(self, request: AiQueryRequest) -> AiQueryResponse:
        record = self.repository.get(request.repository_id)
        if not record:
            raise NotFoundError("Repository not found.", {"repositoryId": request.repository_id})
        config = self._read_config()
        if not config:
            raise ValidationServiceError("AI provider is not configured. Open Settings and save a provider first.")

        context, citations = self._repository_context(record, request.context.selected_file if request.context else None)
        answer = await self._call_provider(config, self._system_prompt(record.name, context), request.query)
        return AiQueryResponse(
            message=AiMessage(role="assistant", content=answer, timestamp=datetime.now(UTC), citations=citations),
            suggestions=[
                "Explain the main architecture boundaries.",
                "What files should I read first?",
                "What are the highest-risk engineering issues?",
            ],
        )

    def _read_config(self) -> AiProviderConfig | None:
        if not self.path.exists():
            return None
        try:
            return AiProviderConfig.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    async def _call_provider(self, config: AiProviderConfig, system_prompt: str, user_prompt: str) -> str:
        if config.provider != "ollama" and not config.api_key:
            raise ValidationServiceError("API key is required for the selected AI provider.")

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                if config.provider == "openai":
                    payload = {"model": config.model or DEFAULT_MODELS["openai"], "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
                    response = await client.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {config.api_key}"}, json=payload)
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]
                if config.provider == "anthropic":
                    payload = {"model": config.model or DEFAULT_MODELS["anthropic"], "max_tokens": 1200, "system": system_prompt, "messages": [{"role": "user", "content": user_prompt}]}
                    response = await client.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": config.api_key or "", "anthropic-version": "2023-06-01"}, json=payload)
                    response.raise_for_status()
                    parts = response.json().get("content", [])
                    return "\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()
                if config.provider == "gemini":
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model or DEFAULT_MODELS['gemini']}:generateContent"
                    payload = {"contents": [{"parts": [{"text": f"{system_prompt}\n\nQuestion: {user_prompt}"}]}]}
                    response = await client.post(url, params={"key": config.api_key}, json=payload)
                    response.raise_for_status()
                    parts = response.json()["candidates"][0]["content"]["parts"]
                    return "\n".join(part.get("text", "") for part in parts).strip()
                if config.provider == "openrouter":
                    payload = {"model": config.model or DEFAULT_MODELS["openrouter"], "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
                    response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {config.api_key}"}, json=payload)
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]

                base_url = (config.base_url or "http://localhost:11434").rstrip("/")
                payload = {"model": config.model or DEFAULT_MODELS["ollama"], "stream": False, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
                response = await client.post(f"{base_url}/api/chat", json=payload)
                response.raise_for_status()
                return response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc

    def _system_prompt(self, repository_name: str, context: str) -> str:
        return (
            f"You are PARTHA's repository assistant for {repository_name}. "
            "Answer only from the provided repository context when possible. "
            "Mention relevant file paths explicitly and say when evidence is missing.\n\n"
            f"Repository context:\n{context}"
        )

    def _repository_context(self, record, selected_file: str | None) -> tuple[str, list[AiCitation]]:
        repository_intelligence = self.intelligence.from_record(record)
        files = [file.path for file in repository_intelligence.files]
        selected = [path for path in files if selected_file and path == selected_file]
        highlighted = selected or files[:40]
        modules = repository_intelligence.modules[:10]
        dependencies = repository_intelligence.dependencies[:20]
        context_lines = [
            f"Primary language: {repository_intelligence.discovery.primary_language}",
            f"Frameworks: {', '.join(repository_intelligence.discovery.frameworks) if repository_intelligence.discovery.frameworks else 'Not detected'}",
            f"Entry points: {', '.join(repository_intelligence.discovery.entry_points) if repository_intelligence.discovery.entry_points else 'Not found'}",
            "Modules:",
            *[f"- {module.name} ({module.role}, {len(module.files)} files)" for module in modules],
            "Dependencies:",
            *[f"- {dependency.name} {dependency.version}" for dependency in dependencies],
            "Files:",
            *[f"- {path}" for path in highlighted],
        ]
        citations = [
            AiCitation(file=path, start_line=1, end_line=1, content="Repository file path included in analysis context.")
            for path in highlighted[:5]
        ]
        return "\n".join(context_lines), citations
