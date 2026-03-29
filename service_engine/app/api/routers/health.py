from fastapi import APIRouter

router = APIRouter(tags=["infra"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

