"""
Wardrobe upload and list.
POST /api/wardrobe/upload: image file → Cloudinary → HF caption → Groq JSON → Supabase → return item.
GET /api/wardrobe: list items for the current user (MVP: default user).
"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services import cloudinary_service, ai_tagging, wardrobe_db

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 10


class WardrobeUpdate(BaseModel):
    type: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    pattern: str | None = None
    formality: int | None = None
    seasons: list[str] | None = None
    material: str | None = None
    style_tags: list[str] | None = None


@router.post("/upload")
async def upload_wardrobe_item(
    file: UploadFile = File(...),
):
    """
    Upload one wardrobe image. Runs AI tagging (HF + Groq) and stores in Supabase.
    Returns the created wardrobe item (including image_url and attributes).
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Allowed types: JPEG, PNG, WebP. Got {file.content_type}.",
        )
    raw = await file.read()
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {MAX_SIZE_MB} MB).",
        )

    # 1) Cloudinary
    image_url, upload_err = cloudinary_service.upload_image(
        raw, file.content_type or "image/jpeg"
    )
    if not image_url:
        raise HTTPException(
            status_code=502,
            detail=upload_err
            or "Image upload failed. Check CLOUDINARY_* in .env.",
        )

    # 2) AI attributes
    attrs = ai_tagging.recognize_clothing(raw)

    # 3) Save to DB
    row = wardrobe_db.insert_wardrobe_item(
        user_id=wardrobe_db.DEFAULT_USER_ID,
        image_url=image_url,
        type_=attrs.get("type") or "top",
        primary_color=attrs.get("primary_color") or "neutral",
        secondary_color=attrs.get("secondary_color"),
        pattern=attrs.get("pattern") or "solid",
        formality=int(attrs.get("formality", 3)),
        seasons=attrs.get("seasons") or ["spring", "summer", "fall", "winter"],
        material=attrs.get("material") or "unknown",
        style_tags=attrs.get("style_tags") or ["casual"],
    )
    if not row:
        raise HTTPException(
            status_code=502,
            detail="Database save failed. Check Supabase table and .env.",
        )
    return row


@router.get("")
def list_wardrobe(
    user_id: str | None = None,
):
    """List wardrobe items for the user (MVP: default user if user_id omitted)."""
    items = wardrobe_db.list_wardrobe_items(user_id)
    if not user_id and not items:
        # MVP fallback: if legacy rows were inserted under different user IDs,
        # show them so users can recover previously uploaded photos.
        items = wardrobe_db.list_all_wardrobe_items()
    return {"items": items}


@router.patch("/{item_id}")
def patch_wardrobe_item(item_id: str, body: WardrobeUpdate):
    updated = wardrobe_db.update_wardrobe_item(
        item_id=item_id,
        updates=body.model_dump(exclude_unset=True),
        user_id=wardrobe_db.DEFAULT_USER_ID,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Wardrobe item not found or not updated")
    return updated


@router.delete("/{item_id}")
def delete_wardrobe_item(item_id: str):
    ok = wardrobe_db.delete_wardrobe_item(item_id=item_id, user_id=wardrobe_db.DEFAULT_USER_ID)
    if not ok:
        raise HTTPException(status_code=404, detail="Wardrobe item not found")
    return {"ok": True}


@router.post("/{item_id}/retag")
def retag_wardrobe_item(item_id: str, engine: str | None = None, targets: str | None = None):
    """
    Re-run AI tagging using the stored image_url and update the item's attributes.
    """
    item = wardrobe_db.get_wardrobe_item(item_id=item_id, user_id=wardrobe_db.DEFAULT_USER_ID)
    if not item:
        raise HTTPException(status_code=404, detail="Wardrobe item not found")
    image_url = item.get("image_url")
    if not image_url:
        raise HTTPException(status_code=400, detail="Item has no image_url")

    target_list = (
        [t.strip() for t in (targets or "").split(",") if t.strip()]
        if targets is not None
        else []
    )

    use_gemini = (engine or "").lower() in {"gemini", "gemini_flash", "flash"}

    if use_gemini and target_list:
        attrs_list = ai_tagging.recognize_clothing_from_url_gemini_multi(image_url, targets=target_list)
    else:
        one = ai_tagging.recognize_clothing_from_url_gemini(image_url) if use_gemini else ai_tagging.recognize_clothing_from_url(image_url)
        attrs_list = [one]

    # Update existing item with first set of attributes, insert additional items for co-ords
    first = attrs_list[0] if attrs_list else {}
    updated = wardrobe_db.update_wardrobe_item(
        item_id=item_id,
        user_id=wardrobe_db.DEFAULT_USER_ID,
        updates={
            "type": first.get("type") or item.get("type"),
            "primary_color": first.get("primary_color") or item.get("primary_color"),
            "secondary_color": first.get("secondary_color"),
            "pattern": first.get("pattern") or item.get("pattern"),
            "formality": int(first.get("formality", item.get("formality") or 3)),
            "seasons": first.get("seasons") or item.get("seasons") or ["spring", "summer", "fall", "winter"],
            "material": first.get("material") or item.get("material"),
            "style_tags": first.get("style_tags") or item.get("style_tags") or ["casual"],
        },
    )
    if not updated:
        raise HTTPException(status_code=502, detail="Could not update item after retagging")

    created: list[dict] = []
    for extra in attrs_list[1:]:
        row = wardrobe_db.insert_wardrobe_item(
            user_id=wardrobe_db.DEFAULT_USER_ID,
            image_url=image_url,
            type_=extra.get("type") or "other",
            primary_color=extra.get("primary_color") or "unknown",
            secondary_color=extra.get("secondary_color"),
            pattern=extra.get("pattern") or "other",
            formality=int(extra.get("formality", 3)),
            seasons=extra.get("seasons") or ["spring", "summer", "fall", "winter"],
            material=extra.get("material") or "unknown",
            style_tags=extra.get("style_tags") or ["casual"],
        )
        if row:
            created.append(row)

    return {"items": [updated, *created]}
