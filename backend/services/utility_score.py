"""
Utility scoring MVP (PRD US-004).
Given a candidate item and the user's wardrobe + color season:
- compute outfit potential (count compatible pairings)
- compute seasonal versatility
- compute color match score (simple palette rules)
- compute utility score + cost per wear

This is intentionally a rules-based MVP; later we can improve with learned models.
"""

from __future__ import annotations

from dataclasses import dataclass

from services import user_profile, wardrobe_db


PAIRING_RULES: dict[str, list[str]] = {
    "top": ["pants", "jeans", "skirt", "shorts"],
    "t-shirt": ["pants", "jeans", "skirt", "shorts"],
    "shirt": ["pants", "jeans", "skirt", "shorts"],
    "blouse": ["pants", "jeans", "skirt", "shorts"],
    "sweater": ["pants", "jeans", "skirt"],
    "blazer": ["pants", "jeans", "skirt", "dress"],
    "jacket": ["pants", "jeans", "skirt", "dress", "shorts"],
    "coat": ["pants", "jeans", "skirt", "dress"],
    "dress": ["blazer", "jacket", "coat"],
    "skirt": ["top", "t-shirt", "shirt", "blouse", "sweater"],
    "pants": ["top", "t-shirt", "shirt", "blouse", "sweater", "blazer", "jacket"],
    "jeans": ["top", "t-shirt", "shirt", "blouse", "sweater", "blazer", "jacket"],
    "shorts": ["top", "t-shirt", "shirt", "blouse"],
}


def _norm_type(t: str | None) -> str:
    if not t:
        return "other"
    x = t.strip().lower()
    # Normalize common variants
    aliases = {
        "tee": "t-shirt",
        "tshirt": "t-shirt",
        "trousers": "pants",
        "slacks": "pants",
    }
    return aliases.get(x, x)


def _norm_pattern(p: str | None) -> str:
    if not p:
        return "other"
    return p.strip().lower().replace(" ", "_")


def _norm_color(c: str | None) -> str:
    if not c:
        return ""
    return c.strip().lower()


def _color_match_score(color_season: str | None, item_color: str) -> float:
    """
    Minimal MVP mapping. We can expand to 12 seasons + hex matching later.
    """
    c = item_color
    if not c:
        return 0.5

    # Simple rules: keep it lightweight; we can replace with full palettes.json later.
    if color_season in (None, ""):
        return 0.5

    season = color_season.lower()
    # Soft Autumn: warm, earthy, muted
    if season == "soft_autumn":
        best = ["camel", "taupe", "olive", "sage", "terracotta", "cream", "warm grey", "rust", "moss"]
        avoid = ["hot pink", "electric blue", "neon", "pure white"]
    # Soft Summer: cool, muted
    elif season == "soft_summer":
        best = ["lavender", "soft pink", "ash grey", "slate", "cool grey", "dusty blue"]
        avoid = ["orange", "mustard", "neon", "golden yellow"]
    # Warm Spring: warm, clear
    elif season == "warm_spring":
        best = ["coral", "peach", "warm pink", "aqua", "turquoise", "cream"]
        avoid = ["charcoal", "black", "muddy brown"]
    # Cool Winter: cool, high contrast
    elif season == "cool_winter":
        best = ["black", "white", "navy", "emerald", "ruby", "cobalt", "silver"]
        avoid = ["orange", "warm brown", "camel", "mustard"]
    else:
        best, avoid = [], []

    if any(a in c for a in avoid):
        return 0.0
    if any(b in c for b in best):
        return 1.0
    # neutrals
    neutrals = ["black", "white", "grey", "gray", "beige", "cream", "navy", "brown"]
    if any(n in c for n in neutrals):
        return 0.8
    return 0.5


def _pattern_compatible(p1: str, p2: str) -> bool:
    if p1 in ("solid", "") or p2 in ("solid", ""):
        return True
    conflicts = {
        "stripes": {"floral", "geometric", "plaid", "polka_dot"},
        "floral": {"stripes", "geometric", "plaid"},
        "geometric": {"floral", "stripes"},
        "plaid": {"floral", "stripes"},
        "polka_dot": {"stripes", "geometric"},
    }
    return p2 not in conflicts.get(p1, set())


def _formality_ok(f1: int, f2: int) -> bool:
    return abs(int(f1) - int(f2)) <= 2


def outfit_potential(candidate: dict, wardrobe: list[dict]) -> int:
    """
    Count compatible pairings with wardrobe items (MVP: 2-piece compatibility).
    """
    c_type = _norm_type(candidate.get("type"))
    c_pat = _norm_pattern(candidate.get("pattern"))
    c_form = int(candidate.get("formality") or 3)
    compatible = set(PAIRING_RULES.get(c_type, []))
    if not compatible:
        return 0
    count = 0
    for w in wardrobe:
        w_type = _norm_type(w.get("type"))
        if w_type not in compatible:
            continue
        w_form = int(w.get("formality") or 3)
        if not _formality_ok(c_form, w_form):
            continue
        if not _pattern_compatible(c_pat, _norm_pattern(w.get("pattern"))):
            continue
        count += 1
    return count


def seasonal_versatility(candidate: dict) -> float:
    seasons = candidate.get("seasons") or []
    if not isinstance(seasons, list):
        return 0.5
    n = len({s.strip().lower() for s in seasons if isinstance(s, str) and s.strip()})
    return min(max(n / 4.0, 0.0), 1.0)


def score_candidate(candidate: dict) -> dict:
    """
    Main scoring entrypoint for the API.
    """
    wardrobe = wardrobe_db.list_wardrobe_items()
    color_season = user_profile.get_color_season()

    outfits = outfit_potential(candidate, wardrobe)
    outfit_potential_norm = min(outfits / 30.0, 1.0)
    season_norm = seasonal_versatility(candidate)
    color_norm = _color_match_score(color_season, _norm_color(candidate.get("primary_color")))

    # Trend alignment + gap filling: placeholders for MVP.
    trend_alignment = 0.5
    gap_filling = 0.0

    utility = (
        outfit_potential_norm * 0.35
        + season_norm * 0.20
        + color_norm * 0.20
        + trend_alignment * 0.15
        + gap_filling * 0.10
    ) * 100.0

    price = float(candidate.get("price") or 0.0)
    cost_per_wear = round(price / max(outfits, 1), 2) if price else None

    return {
        "score": round(utility, 1),
        "outfit_potential": outfits,
        "outfit_potential_normalized": round(outfit_potential_norm, 2),
        "seasonal_versatility": round(season_norm, 2),
        "color_match": round(color_norm, 2),
        "trend_alignment": round(trend_alignment, 2),
        "gap_filling": round(gap_filling, 2),
        "cost_per_wear": cost_per_wear,
        "color_season": color_season,
    }

