from collections import Counter
from typing import Any

from fastapi import APIRouter

from services import user_profile, wardrobe_db
from services.utility_score import _color_match_score

router = APIRouter(prefix="/analytics", tags=["analytics"])

_SEASONS = ("spring", "summer", "fall", "winter")


def _slot_for(item_type: str | None) -> str:
    t = (item_type or "").strip().lower()
    if t in {"top", "t-shirt", "shirt", "blouse", "sweater", "hoodie", "tank"}:
        return "top"
    if t in {"pants", "jeans", "skirt", "shorts", "leggings"}:
        return "bottom"
    if t in {"shoes", "boots", "sneakers", "sandals", "heels", "loafers", "flats"}:
        return "shoes"
    if t in {"blazer", "jacket", "coat", "cardigan", "vest"}:
        return "layer"
    return "other"


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


@router.get("/overview")
def analytics_overview(user_id: str | None = None):
    items = wardrobe_db.list_wardrobe_items(user_id)
    if not user_id and not items:
        items = wardrobe_db.list_all_wardrobe_items()

    total = len(items)
    if total == 0:
        return {
            "total_items": 0,
            "wardrobe_utilization_pct": 0,
            "most_worn_category": None,
            "color_palette_adherence_pct": 0,
            "seasonal_coverage_pct": {s: 0 for s in _SEASONS},
            "closet_gaps": [
                "No wardrobe items found yet. Upload items to unlock live analytics.",
            ],
            "data_notes": {
                "utilization_source": "times_worn",
                "most_worn_source": "times_worn",
                "fallback_used": True,
            },
        }

    color_season = user_profile.get_color_season()
    slot_counts = Counter(_slot_for(str(it.get("type") or "")) for it in items)

    worn_counts = [_safe_int(it.get("times_worn")) for it in items if it.get("times_worn") is not None]
    has_wear_data = len(worn_counts) > 0
    if has_wear_data:
        wardrobe_utilization_pct = round(
            100.0 * sum(1 for w in worn_counts if w > 0) / max(len(worn_counts), 1),
            1,
        )
        most_worn_category = None
        most_worn_total = -1
        category_sums: dict[str, int] = {}
        for it in items:
            if it.get("times_worn") is None:
                continue
            t = str(it.get("type") or "other").strip().lower()
            category_sums[t] = category_sums.get(t, 0) + _safe_int(it.get("times_worn"))
        for cat, total_worn in category_sums.items():
            if total_worn > most_worn_total:
                most_worn_total = total_worn
                most_worn_category = cat
    else:
        # Fallback when times_worn is absent in schema.
        wardrobe_utilization_pct = round(min(100.0, total * 4.0), 1)
        most_worn_category = Counter(str(it.get("type") or "other").strip().lower() for it in items).most_common(1)[0][0]

    color_scores = []
    if color_season:
        for it in items:
            color_scores.append(_color_match_score(color_season, str(it.get("primary_color") or "")))
    color_palette_adherence_pct = (
        round((sum(color_scores) / max(len(color_scores), 1)) * 100.0, 1) if color_scores else 0.0
    )

    season_counts: dict[str, int] = {s: 0 for s in _SEASONS}
    for it in items:
        seasons = it.get("seasons") or []
        if not isinstance(seasons, list):
            continue
        normalized = {str(s).strip().lower() for s in seasons if str(s).strip()}
        for s in _SEASONS:
            if s in normalized:
                season_counts[s] += 1
    seasonal_coverage_pct = {
        s: round(100.0 * season_counts[s] / max(total, 1), 1) for s in _SEASONS
    }

    closet_gaps: list[str] = []
    if slot_counts.get("top", 0) < 4:
        closet_gaps.append("Limited tops variety for rotating outfits across a week.")
    if slot_counts.get("bottom", 0) < 3:
        closet_gaps.append("Add one or two more bottoms to unlock more distinct outfit combinations.")
    if slot_counts.get("shoes", 0) < 2:
        closet_gaps.append("Only one or no shoe option detected; outfits will repeat footwear frequently.")
    rain_ready = sum(
        1
        for it in items
        if _slot_for(str(it.get("type") or "")) == "layer"
        and str(it.get("material") or "").strip().lower() in {"nylon", "polyester", "gore-tex", "waterproof"}
    )
    if rain_ready == 0:
        closet_gaps.append("No clearly rain-ready outer layer detected for wet weather days.")
    formal_items = sum(1 for it in items if _safe_int(it.get("formality")) >= 4)
    if formal_items < 2:
        closet_gaps.append("Limited business/formal pieces for presentations or evening events.")
    if not closet_gaps:
        closet_gaps.append("Coverage looks balanced across slots and seasons for day-to-day styling.")

    return {
        "total_items": total,
        "wardrobe_utilization_pct": wardrobe_utilization_pct,
        "most_worn_category": most_worn_category,
        "color_palette_adherence_pct": color_palette_adherence_pct,
        "seasonal_coverage_pct": seasonal_coverage_pct,
        "closet_gaps": closet_gaps[:4],
        "data_notes": {
            "utilization_source": "times_worn" if has_wear_data else "fallback_from_inventory",
            "most_worn_source": "times_worn" if has_wear_data else "type_frequency",
            "fallback_used": not has_wear_data,
        },
    }

