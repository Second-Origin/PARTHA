import json
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_ai_service, get_current_user
from app.api.openapi import documented_responses, error_responses, response_example
from app.schemas.ai import AiProviderConfig, AiProviderPublicConfig, AiProviderTestRequest, AiProviderTestResponse, AiQueryRequest, AiQueryResponse
from app.services.ai_service import AiService

# Every AI route requires auth; the repository and the provider config are both
# owner-scoped in the orchestrator, so a query can never run against another
# user's repository or spend their provider key.
router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(get_current_user)])

_REPOSITORY_ID = "11111111-1111-1111-1111-111111111111"
_PUBLIC_CONFIG_EXAMPLE = {
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "baseUrl": None,
    "hasApiKey": True,
    "apiKeyLast4": "1234",
}
_CONFIG_REQUEST_EXAMPLE = {
    "summary": "Configure an OpenAI provider",
    "value": {"provider": "openai", "apiKey": "sk-example-not-a-real-key", "model": "gpt-4.1-mini"},
}
_TEST_REQUEST_EXAMPLE = {
    "summary": "Test the saved provider configuration",
    "value": {"provider": "openai", "model": "gpt-4.1-mini"},
}
_QUERY_REQUEST_EXAMPLE = {
    "summary": "Ask about an imported repository",
    "value": {"repositoryId": _REPOSITORY_ID, "query": "Which modules handle authentication?"},
}
_QUERY_RESPONSE_EXAMPLE = {
    "message": {
        "role": "assistant",
        "content": "Authentication is handled by the auth module.",
        "timestamp": "2026-07-17T00:00:00Z",
        "citations": [],
    },
    "suggestions": ["Show the authentication routes"],
}


@router.get(
    "/config",
    response_model=AiProviderPublicConfig,
    responses=documented_responses(
        200,
        "Saved provider configuration without the full API key.",
        _PUBLIC_CONFIG_EXAMPLE,
        401,
        429,
        500,
    ),
)
def get_ai_config(service: AiService = Depends(get_ai_service)) -> AiProviderPublicConfig:
    return service.get_config()


@router.put(
    "/config",
    response_model=AiProviderPublicConfig,
    responses=documented_responses(
        200,
        "Provider configuration saved without returning the full API key.",
        _PUBLIC_CONFIG_EXAMPLE,
        401,
        422,
        429,
        500,
    ),
)
def save_ai_config(
    config: Annotated[AiProviderConfig, Body(openapi_examples={"provider": _CONFIG_REQUEST_EXAMPLE})],
    service: AiService = Depends(get_ai_service),
) -> AiProviderPublicConfig:
    return service.save_config(config)


@router.post(
    "/test",
    response_model=AiProviderTestResponse,
    responses=documented_responses(
        200,
        "Provider connectivity result.",
        {"ok": True, "message": "Provider connection succeeded.", "checkedAt": "2026-07-17T00:00:00Z"},
        401,
        422,
        429,
        502,
        500,
    ),
)
async def test_ai_config(
    request: Annotated[AiProviderTestRequest, Body(openapi_examples={"connection": _TEST_REQUEST_EXAMPLE})],
    service: AiService = Depends(get_ai_service),
) -> AiProviderTestResponse:
    return await service.test_connection(request)


@router.post(
    "/query",
    response_model=AiQueryResponse,
    responses=documented_responses(
        200,
        "Repository-aware AI response.",
        _QUERY_RESPONSE_EXAMPLE,
        401,
        404,
        422,
        429,
        502,
        500,
    ),
)
async def query_ai(
    request: Annotated[AiQueryRequest, Body(openapi_examples={"repository-question": _QUERY_REQUEST_EXAMPLE})],
    service: AiService = Depends(get_ai_service),
) -> AiQueryResponse:
    return await service.query(request)


@router.post(
    "/stream",
    response_class=StreamingResponse,
    responses={
        200: response_example(
            "Server-sent events containing a repository-aware AI response.",
            'data: {"type":"content","content":"Authentication "}\\n\\n'
            'data: {"type":"done"}\\n\\n',
            media_type="text/event-stream",
            schema={"type": "string"},
        ),
        **error_responses(401, 404, 422, 429, 502, 500),
    },
)
async def stream_ai(
    request: Annotated[AiQueryRequest, Body(openapi_examples={"repository-question": _QUERY_REQUEST_EXAMPLE})],
    service: AiService = Depends(get_ai_service),
) -> StreamingResponse:
    # Resolve the answer BEFORE returning StreamingResponse. service.query runs
    # ownership scoping and provider-config validation, so a cross-owner request
    # (404) or a missing provider key (422) must surface as a normal error
    # response here — not inside the generator, where 200 headers would already
    # have been sent and the failure could only abort a stream that "succeeded".
    # query already computes the full response before any word is emitted, so
    # awaiting it here changes nothing on the success path.
    response = await service.query(request)

    async def events():
        for word in response.message.content.split(" "):
            yield f"data: {json.dumps({'type': 'content', 'content': word + ' '})}\n\n"
        for citation in response.message.citations or []:
            yield f"data: {json.dumps({'type': 'citation', 'citation': citation.model_dump(mode='json', by_alias=True)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
