"""User profile: color season from quiz."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import user_profile

router = APIRouter(prefix="/user", tags=["user"])


class ColorSeasonBody(BaseModel):
    color_season: str


@router.get("/color-season")
def get_color_season(user_id: str | None = None):
    """Get saved color season for current user (MVP: default user)."""
    season = user_profile.get_color_season(user_id)
    return {"color_season": season}


@router.put("/color-season")
def put_color_season(body: ColorSeasonBody, user_id: str | None = None):
    """Save color season (e.g. after quiz). Requires user_profiles table in Supabase."""
    if not body.color_season or not body.color_season.strip():
        raise HTTPException(status_code=400, detail="color_season is required")
    ok = user_profile.set_color_season(body.color_season.strip(), user_id)
    if not ok:
        raise HTTPException(
            status_code=503,
            detail="Could not save. Run supabase_user_profiles.sql in Supabase SQL Editor (see backend/SETUP.md).",
        )
    return {"ok": True, "color_season": body.color_season}
