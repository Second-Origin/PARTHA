from fastapi import APIRouter

router = APIRouter()


def audit(handler):
    return handler


@audit
@router.get("/health")
def health():
    return {"status": "ok"}
