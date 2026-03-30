"""
Shopping recommendations: persisted candidate items + UtilityScorer (sync, no Gemini on list).
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import settings
from services.enhanced_utility_score import adjust_score_with_preferences
from services.shopping_recommendations_db import (
    delete_recommendation,
    insert_recommendation,
    list_recommendations,
)
from services.utility_score import score_candidate
from services.wardrobe_db import DEFAULT_USER_ID

router = APIRouter(prefix="/shopping", tags=["shopping"])


def _supabase_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_key)


def _row_to_candidate(row: dict[str, Any]) -> dict[str, Any]:
    price = row.get("price")
    if price is not None:
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = None
    seasons = row.get("seasons")
    if not isinstance(seasons, list):
        seasons = []
    return {
        "type": (row.get("type") or "other").strip(),
        "primary_color": (row.get("primary_color") or "").strip() or None,
        "secondary_color": row.get("secondary_color"),
        "pattern": (row.get("pattern") or "solid").strip(),
        "formality": int(row.get("formality") or 3),
        "seasons": seasons,
        "material": row.get("material"),
        "style_tags": list(row.get("style_tags") or []) if row.get("style_tags") else None,
        "price": price,
    }


_DEFAULT_PREFS: dict[str, Any] = {
    "preferred_colors": {},
    "preferred_types": {},
    "interaction_history": [],
}


def _score_row(row: dict[str, Any], user_preferences: dict[str, Any] | None) -> dict[str, Any]:
    item = _row_to_candidate(row)
    prefs = user_preferences if isinstance(user_preferences, dict) else _DEFAULT_PREFS
    base = score_candidate(item)
    adjusted = adjust_score_with_preferences(float(base["score"]), item, prefs)
    return {
        "utility_score": round(float(base["score"]), 1),
        "adjusted_score": float(adjusted),
        "cost_per_wear": base.get("cost_per_wear"),
    }


class ShoppingRecommendationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., min_length=1, max_length=50)
    primary_color: str | None = None
    secondary_color: str | None = None
    pattern: str | None = "solid"
    formality: int | None = Field(default=3, ge=1, le=5)
    seasons: list[str] | None = None
    material: str | None = None
    style_tags: list[str] | None = None
    price: float | None = Field(default=None, ge=0)
    link: str | None = None
    image_url: str | None = None


@router.get("/recommendations")
def get_recommendations():
    """
    List saved recommendations with live utility_score / adjusted_score / cost_per_wear
    (wardrobe-based scorer + preference adjustment; no Gemini on this endpoint).
    """
    if not _supabase_configured():
        return {"configured": False, "user_id": DEFAULT_USER_ID, "items": []}

    rows = list_recommendations()
    out: list[dict[str, Any]] = []
    for row in rows:
        scores = _score_row(row, None)
        out.append(
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "price": float(row["price"]) if row.get("price") is not None else None,
                "link": row.get("link"),
                "image_url": row.get("image_url"),
                **scores,
            }
        )
    return {"configured": True, "user_id": DEFAULT_USER_ID, "items": out}


@router.post("/recommendations")
def create_recommendation(body: ShoppingRecommendationCreate):
    if not _supabase_configured():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured (set SUPABASE_URL and SUPABASE_KEY).",
        )
    dumped = body.model_dump(exclude_none=True)
    row = insert_recommendation(None, dumped)
    if not row:
        raise HTTPException(
            status_code=500,
            detail="Insert failed. Ensure table shopping_recommendations exists (run supabase_shopping_recommendations.sql).",
        )
    scores = _score_row(row, None)
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "price": float(row["price"]) if row.get("price") is not None else None,
        "link": row.get("link"),
        "image_url": row.get("image_url"),
        **scores,
    }


@router.delete("/recommendations/{rec_id}")
def remove_recommendation(rec_id: str):
    if not _supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured.")
    if not delete_recommendation(rec_id):
        raise HTTPException(status_code=404, detail="Recommendation not found or could not delete.")
    return {"ok": True}
