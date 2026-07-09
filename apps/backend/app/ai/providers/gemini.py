from app.ai.providers.http import post, require_api_key
from app.ai.types import DEFAULT_MODELS, AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import ExternalServiceError


class GeminiProvider:
    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        require_api_key(config)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model or DEFAULT_MODELS['gemini']}:generateContent"
        payload = {"contents": [{"parts": [{"text": f"{prompt.system_prompt}\n\nQuestion: {prompt.user_prompt}"}]}]}
        response = await post(config, url, params={"key": config.api_key}, json=payload)
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            return AiProviderResponse(content="\n".join(part.get("text", "") for part in parts).strip())
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
