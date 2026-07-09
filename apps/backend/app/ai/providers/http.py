import httpx

from app.ai.types import AiProviderConfig
from app.core.exceptions import ExternalServiceError, ValidationServiceError


def require_api_key(config: AiProviderConfig) -> None:
    if not config.api_key:
        raise ValidationServiceError("API key is required for the selected AI provider.")


async def post(config: AiProviderConfig, url: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, **kwargs)
            response.raise_for_status()
            return response
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
