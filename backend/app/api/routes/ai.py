import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_ai_service
from app.schemas.ai import AiProviderConfig, AiProviderPublicConfig, AiProviderTestRequest, AiProviderTestResponse, AiQueryRequest, AiQueryResponse
from app.services.ai_service import AiService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/config", response_model=AiProviderPublicConfig)
def get_ai_config(service: AiService = Depends(get_ai_service)) -> AiProviderPublicConfig:
    return service.get_config()


@router.put("/config", response_model=AiProviderPublicConfig)
def save_ai_config(config: AiProviderConfig, service: AiService = Depends(get_ai_service)) -> AiProviderPublicConfig:
    return service.save_config(config)


@router.post("/test", response_model=AiProviderTestResponse)
async def test_ai_config(request: AiProviderTestRequest, service: AiService = Depends(get_ai_service)) -> AiProviderTestResponse:
    return await service.test_connection(request)


@router.post("/query", response_model=AiQueryResponse)
async def query_ai(request: AiQueryRequest, service: AiService = Depends(get_ai_service)) -> AiQueryResponse:
    return await service.query(request)


@router.post("/stream")
async def stream_ai(request: AiQueryRequest, service: AiService = Depends(get_ai_service)) -> StreamingResponse:
    async def events():
        response = await service.query(request)
        for word in response.message.content.split(" "):
            yield f"data: {json.dumps({'type': 'content', 'content': word + ' '})}\n\n"
        for citation in response.message.citations or []:
            yield f"data: {json.dumps({'type': 'citation', 'citation': citation.model_dump(mode='json', by_alias=True)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
