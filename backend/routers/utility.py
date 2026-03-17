from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.utility_score import score_candidate

router = APIRouter(prefix="/utility", tags=["utility"])


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


@router.post("/score")
def score(body: CandidateItem):
    try:
        return score_candidate(body.model_dump())
    except Exception:
        raise HTTPException(status_code=500, detail="Scoring failed")

