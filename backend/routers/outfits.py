from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services import cloudinary_service, ai_tagging
from services import wear_logs_db
from services.outfit_generator import generate_outfits

router = APIRouter(prefix="/outfits", tags=["outfits"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 10


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
    image_url: str | None = None


class GenerateOutfitsBody(BaseModel):
    occasion: str
    weather_temp: int | None = None
    weather_conditions: str | None = None
    vibe: str | None = None
    engine: str | None = None
    candidate: CandidateItem | None = None
    """When True and candidate fills top/bottom/shoes, that slot uses the hypothetical (photo + tags)."""
    include_hypothetical: bool = False


class WearLogBody(BaseModel):
    item_ids: list[str]
    worn_on: str | None = None
    source: str | None = "outfit_card"


@router.post("/hypothetical-photo")
async def tag_hypothetical_photo(file: UploadFile = File(...)):
    """
    Upload a photo of a piece you're considering buying. Cloudinary + Gemini tagging (same pipeline as wardrobe).
    Does not add the item to Wardrobe — returns tags + image URL for the Outfits flow only.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Allowed types: JPEG, PNG, WebP. Got {file.content_type}.",
        )
    raw = await file.read()
    if len(raw) / (1024 * 1024) > MAX_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_SIZE_MB} MB).")

    image_url, upload_err = cloudinary_service.upload_image(
        raw, file.content_type or "image/jpeg"
    )
    if not image_url:
        raise HTTPException(status_code=502, detail=upload_err or "Image upload failed. Check CLOUDINARY_* in .env.")

    attrs = ai_tagging.recognize_clothing_gemini(raw, mime_type=file.content_type or "image/jpeg")
    candidate = {
        "type": attrs.get("type") or "top",
        "primary_color": attrs.get("primary_color"),
        "secondary_color": attrs.get("secondary_color"),
        "pattern": attrs.get("pattern") or "solid",
        "formality": int(attrs.get("formality", 3)),
        "seasons": attrs.get("seasons") or ["spring", "summer", "fall", "winter"],
        "material": attrs.get("material") or "unknown",
        "style_tags": attrs.get("style_tags") or ["casual"],
        "image_url": image_url,
    }
    return {"image_url": image_url, "candidate": candidate}


@router.post("/generate")
async def generate(body: GenerateOutfitsBody):
    try:
        payload = body.model_dump()
        # LLM-first mode for outfit generation.
        payload["engine"] = "react"
        return await generate_outfits(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Outfit generation failed: {e}")


@router.post("/wear-log")
async def log_wear(body: WearLogBody):
    # Ignore hypothetical placeholder IDs; only persist real wardrobe IDs.
    item_ids = [i for i in body.item_ids if i and str(i) != "hypothetical" and not str(i).startswith("hypothetical::")]
    if not item_ids:
        raise HTTPException(status_code=400, detail="No wardrobe item IDs provided to log.")
    row = wear_logs_db.insert_wear_log(item_ids=item_ids, source=body.source or "outfit_card")
    if not row:
        raise HTTPException(
            status_code=502,
            detail="Could not save wear log. Ensure wear_logs table exists (run supabase_wear_logs.sql).",
        )
    return {"ok": True, "wear_log": row}

