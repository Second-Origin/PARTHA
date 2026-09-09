import anyio
import httpx

from app.ai.providers.http import ProviderHttpSender, post
from app.ai.types import DEFAULT_MODELS, AiProviderConfig, AiProviderResponse, PromptBundle
from app.core.exceptions import ExternalServiceError

# Ollama runs inference on the same machine PARTHA itself runs on -- unlike a
# hosted provider (OpenAI, Anthropic, Gemini, OpenRouter), a concurrent
# request here competes with the user's own machine for CPU and memory, not
# with someone else's infrastructure, so this limit stays specific to this
# provider rather than living in the shared post() transport (#414).
#
# Measured directly against a real Ollama instance: its own backend already
# serializes actual token generation to one request at a time by default, so
# letting more requests through here doesn't get anything done faster -- it
# only means more requests are simultaneously held open, each consuming its
# own memory while it waits its turn, and the elevated CPU/memory load runs
# as one long unbroken stretch instead of several shorter ones with recovery
# gaps between them. A single local machine has no spare parallel headroom
# to give this, and Ollama isn't going to use extra concurrency for extra
# throughput anyway, so this is capped to exactly 1. A request beyond the
# limit queues and waits -- it never fails or gets rejected; this is
# resource management, not a rate limit.
#
# anyio.Semaphore rather than asyncio.Semaphore: a module-level
# asyncio.Semaphore permanently binds itself to whichever event loop first
# contends it, which is a non-issue for the one persistent loop a real
# server runs on, but breaks the moment two separate loops ever contend it
# (a real hazard for a shared, importable module-level object). anyio's
# version is the one already used elsewhere in this provider layer
# (app/ai/providers/http.py) and doesn't have that failure mode.
_MAX_CONCURRENT_REQUESTS = 1
_concurrency_limit = anyio.Semaphore(_MAX_CONCURRENT_REQUESTS)

# The shared sender's 60s default is sized for a hosted API's request/response.
# Ollama is neither: the first call after startup (or after another model was
# loaded) pulls the model into memory before a single token is generated, and
# the generation itself runs on whatever CPU/GPU the user's own machine has.
# A review-sized completion routinely exceeds 60s that way -- entirely
# healthy, not a stuck request -- and cutting it off there is the "it hangs
# then fails" symptom this replaces. So:
#   * connect: 10s. Ollama is either up on the LAN/loopback (connects fast) or
#     it isn't; a wrong/unreachable base URL should fail quickly, not after a
#     long minute, so this stays tight while the read budget is loosened.
#   * read: 10 minutes. Bounds a genuinely wedged server without amputating a
#     legitimately slow local generation.
#   * write/pool: modest; the request body is small and the pool is unshared.
_LOCAL_INFERENCE_TIMEOUT = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)


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
        async with _concurrency_limit:
            response = await post(
                config,
                f"{base_url}/api/chat",
                sender=self.sender,
                timeout=_LOCAL_INFERENCE_TIMEOUT,
                json=payload,
            )
        try:
            return AiProviderResponse(content=response.json()["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("AI provider request failed.", {"provider": config.provider}) from exc
