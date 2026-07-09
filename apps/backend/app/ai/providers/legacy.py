import httpx

from app.ai.types import DEFAULT_MODELS, AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import ExternalServiceError, ValidationServiceError


class LegacyProvider:
    async def complete(self, config: AiProviderConfig, prompt: PromptBundle) -> AiProviderResponse:
        if config.provider != "ollama" and not config.api_key:
            raise ValidationServiceError("API key is required for the selected AI provider.")

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                if config.provider == "openai":
                    payload = {
                        "model": config.model or DEFAULT_MODELS["openai"],
                        "messages": [
                            {"role": "system", "content": prompt.system_prompt},
                            {"role": "user", "content": prompt.user_prompt},
                        ],
                    }
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {config.api_key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    return AiProviderResponse(content=response.json()["choices"][0]["message"]["content"])
                if config.provider == "anthropic":
                    payload = {
                        "model": config.model or DEFAULT_MODELS["anthropic"],
                        "max_tokens": 1200,
                        "system": prompt.system_prompt,
                        "messages": [{"role": "user", "content": prompt.user_prompt}],
                    }
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": config.api_key or "", "anthropic-version": "2023-06-01"},
                        json=payload,
                    )
                    response.raise_for_status()
                    parts = response.json().get("content", [])
                    return AiProviderResponse(
                        content="\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()
                    )
                if config.provider == "gemini":
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model or DEFAULT_MODELS['gemini']}:generateContent"
                    payload = {"contents": [{"parts": [{"text": f"{prompt.system_prompt}\n\nQuestion: {prompt.user_prompt}"}]}]}
                    response = await client.post(url, params={"key": config.api_key}, json=payload)
                    response.raise_for_status()
                    parts = response.json()["candidates"][0]["content"]["parts"]
                    return AiProviderResponse(content="\n".join(part.get("text", "") for part in parts).strip())
                if config.provider == "openrouter":
                    payload = {
                        "model": config.model or DEFAULT_MODELS["openrouter"],
                        "messages": [
                            {"role": "system", "content": prompt.system_prompt},
                            {"role": "user", "content": prompt.user_prompt},
                        ],
                    }
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {config.api_key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    return AiProviderResponse(content=response.json()["choices"][0]["message"]["content"])

                base_url = (config.base_url or "http://localhost:11434").rstrip("/")
                payload = {
                    "model": config.model or DEFAULT_MODELS["ollama"],
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": prompt.system_prompt},
                        {"role": "user", "content": prompt.user_prompt},
                    ],
                }
                response = await client.post(f"{base_url}/api/chat", json=payload)
                response.raise_for_status()
                return AiProviderResponse(content=response.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
