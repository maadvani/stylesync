from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from services.outfit_generator import generate_outfits

router = APIRouter(prefix="/outfits", tags=["outfits"])


class CandidateItem(BaseModel):
    type: str
    primary_color: str | None = None
    secondary_color: str | None = None
    pattern: str | None = None
    formality: int | None = 3
    seasons: list[str] | None = None
    material: str | None = None
    style_tags: list[str] | None = None
    price: float | None = None


class GenerateOutfitsBody(BaseModel):
    occasion: str
    weather_temp: int | None = None
    weather_conditions: str | None = None
    vibe: str | None = None
    engine: str | None = None
    candidate: CandidateItem


@router.post("/generate")
async def generate(body: GenerateOutfitsBody):
    try:
        payload = body.model_dump()
        engine = (payload.get("engine") or "").strip().lower()
        if engine not in {"react", "rules"}:
            payload["engine"] = "react" if settings.outfits_react_enabled else "rules"
        return await generate_outfits(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Outfit generation failed: {e}")

