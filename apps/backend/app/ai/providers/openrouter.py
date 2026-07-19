from app.ai.providers.http import ProviderHttpSender, post, require_api_key
from app.ai.types import DEFAULT_MODELS, AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import ExternalServiceError


class OpenRouterProvider:
    def __init__(self, sender: ProviderHttpSender | None = None) -> None:
        self.sender = sender

    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        require_api_key(config)
        payload = {
            "model": config.model or DEFAULT_MODELS["openrouter"],
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": prompt.user_prompt},
            ],
        }
        response = await post(
            config,
            "https://openrouter.ai/api/v1/chat/completions",
            sender=self.sender,
            headers={"Authorization": f"Bearer {config.api_key}"},
            json=payload,
        )
        try:
            return AiProviderResponse(content=response.json()["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
