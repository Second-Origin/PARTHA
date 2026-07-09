from app.ai.providers.http import post, require_api_key
from app.ai.types import DEFAULT_MODELS, AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import ExternalServiceError


class AnthropicProvider:
    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        require_api_key(config)
        payload = {
            "model": config.model or DEFAULT_MODELS["anthropic"],
            "max_tokens": 1200,
            "system": prompt.system_prompt,
            "messages": [{"role": "user", "content": prompt.user_prompt}],
        }
        response = await post(
            config,
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": config.api_key or "", "anthropic-version": "2023-06-01"},
            json=payload,
        )
        try:
            parts = response.json().get("content", [])
            return AiProviderResponse(
                content="\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
