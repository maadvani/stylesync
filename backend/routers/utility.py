from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel

from services.utility_score import score_candidate
from services import ai_tagging
from services import user_profile as user_profile_service
from services.enhanced_utility_score import enhanced_utility_score

router = APIRouter(prefix="/utility", tags=["utility"])


def _parse_optional_price_str(raw: str | None) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v >= 0 else None


def _price_from_upload(
    form_price: str | None,
    query_price: float | None,
) -> float | None:
    """Multipart form field `price` takes precedence over ?price= query."""
    p = _parse_optional_price_str(form_price)
    if p is not None:
        return p
    if query_price is not None and query_price >= 0:
        return float(query_price)
    return None


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


class EnhancedUtilityBody(BaseModel):
    """Payload for additive enhanced scoring (base score unchanged)."""

    item: CandidateItem
    user_profile: dict | None = None
    wardrobe: list | None = None
    user_preferences: dict | None = None
    user_trends: list | None = None
    wardrobe_analytics: dict | None = None


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 10


@router.post("/score")
def score(body: CandidateItem):
    try:
        return score_candidate(body.model_dump())
    except Exception:
        raise HTTPException(status_code=500, detail="Scoring failed")


@router.post("/score-from-image")
async def score_from_image(
    file: UploadFile = File(...),
    price: str | None = Form(default=None),
    price_query: float | None = Query(default=None),
):
    """
    Upload a clothing photo:
    image -> AI feature extraction -> utility scoring.
    """
    price_f = _price_from_upload(price, price_query)
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Allowed types: JPEG, PNG, WebP. Got {file.content_type}.",
        )

    raw = await file.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_SIZE_MB} MB).")

    # AI tagging already returns the candidate schema the utility scorer expects.
    attrs = ai_tagging.recognize_clothing(raw)
    attrs["price"] = price_f

    try:
        return score_candidate(attrs)
    except Exception:
        raise HTTPException(status_code=500, detail="Scoring failed")


@router.post("/enhanced-from-image")
async def enhanced_from_image(
    file: UploadFile = File(...),
    price: str | None = Form(default=None),
    price_query: float | None = Query(default=None),
):
    """
    Upload a clothing photo → AI attributes → enhanced utility (base + preferences + AI explanation).
    """
    price_f = _price_from_upload(price, price_query)
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Allowed types: JPEG, PNG, WebP. Got {file.content_type}.",
        )

    raw = await file.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_SIZE_MB} MB).")

    attrs = ai_tagging.recognize_clothing(raw)
    attrs["price"] = price_f

    profile: dict = {}
    cs = user_profile_service.get_color_season()
    if cs:
        profile["color_season"] = cs

    prefs = {
        "preferred_colors": {},
        "preferred_types": {},
        "interaction_history": [],
    }

    try:
        return await enhanced_utility_score(
            item=attrs,
            user_profile=profile,
            wardrobe=[],
            user_preferences=prefs,
            user_trends=[],
            wardrobe_analytics={},
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Enhanced scoring failed")


@router.post("/enhanced")
async def score_enhanced(body: EnhancedUtilityBody):
    """
    Base utility score (unchanged) + preference-adjusted score + Gemini explanation.
    """
    item = body.item.model_dump()
    profile = dict(body.user_profile or {})
    if profile.get("color_season") in (None, ""):
        cs = user_profile_service.get_color_season()
        if cs:
            profile["color_season"] = cs

    wardrobe = body.wardrobe if body.wardrobe is not None else []
    prefs = body.user_preferences or {
        "preferred_colors": {},
        "preferred_types": {},
        "interaction_history": [],
    }
    trends = body.user_trends or []
    analytics = body.wardrobe_analytics or {}

    try:
        return await enhanced_utility_score(
            item=item,
            user_profile=profile,
            wardrobe=wardrobe,
            user_preferences=prefs,
            user_trends=trends,
            wardrobe_analytics=analytics,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Enhanced scoring failed")

