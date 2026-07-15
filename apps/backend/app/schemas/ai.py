from datetime import UTC, datetime
from typing import Literal

from app.schemas.base import CamelModel

AiProvider = Literal["openai", "anthropic", "gemini", "openrouter", "ollama"]


class AiCitation(CamelModel):
    file: str
    start_line: int = 1
    end_line: int = 1
    content: str


class AiMessage(CamelModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    citations: list[AiCitation] | None = None


class AiQueryContext(CamelModel):
    selected_node_id: str | None = None
    selected_file: str | None = None
    conversation_history: list[AiMessage] | None = None


class AiQueryRequest(CamelModel):
    repository_id: str
    query: str
    context: AiQueryContext | None = None


class AiQueryResponse(CamelModel):
    message: AiMessage
    suggestions: list[str] = []


class AiProviderConfig(CamelModel):
    provider: AiProvider
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


class AiProviderPublicConfig(CamelModel):
    provider: AiProvider | None = None
    model: str | None = None
    base_url: str | None = None
    has_api_key: bool = False
    # Write-only contract: the stored API key is never returned in full. The
    # last four characters are surfaced so the UI can confirm which key is
    # saved without ever exposing the secret.
    api_key_last4: str | None = None


class AiProviderTestRequest(CamelModel):
    provider: AiProvider | None = None
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


class AiProviderTestResponse(CamelModel):
    ok: bool
    message: str
    checked_at: datetime = datetime.now(UTC)
