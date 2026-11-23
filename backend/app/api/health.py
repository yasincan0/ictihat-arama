from fastapi import APIRouter

router = APIRouter(tags=["sistem"])


@router.get("/health")
def health() -> dict[str, str]:
    """Servisin ayakta olduğunu bildirir."""
    return {"status": "ok"}
