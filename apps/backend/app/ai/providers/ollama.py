from app.ai.providers.http import post
from app.ai.types import DEFAULT_MODELS, AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import ExternalServiceError


class OllamaProvider:
    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        base_url = (config.base_url or "http://localhost:11434").rstrip("/")
        payload = {
            "model": config.model or DEFAULT_MODELS["ollama"],
            "stream": False,
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": prompt.user_prompt},
            ],
        }
        response = await post(config, f"{base_url}/api/chat", json=payload)
        try:
            return AiProviderResponse(content=response.json()["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
