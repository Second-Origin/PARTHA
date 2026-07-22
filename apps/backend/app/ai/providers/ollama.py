from app.ai.providers.http import ProviderHttpSender, post
from app.ai.types import DEFAULT_MODELS, AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import ExternalServiceError


class OllamaProvider:
    def __init__(self, sender: ProviderHttpSender | None = None) -> None:
        self.sender = sender

    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        # There is intentionally no localhost fallback.  A local endpoint is a
        # deployment-owned decision that must be explicitly approved by policy.
        base_url = (config.base_url or "").rstrip("/")
        payload = {
            "model": config.model or DEFAULT_MODELS["ollama"],
            "stream": False,
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": prompt.user_prompt},
            ],
        }
        response = await post(config, f"{base_url}/api/chat", sender=self.sender, json=payload)
        try:
            return AiProviderResponse(content=response.json()["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
