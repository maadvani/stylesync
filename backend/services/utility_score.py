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


# When the vision model omits `seasons`, these types are treated as year-round staples.
_YEAR_ROUND_TYPES = frozenset(
    {"jeans", "pants", "shorts", "t-shirt", "shirt", "blouse", "sweater", "top"}
)

# Winter family seasons share high-contrast cool palette rules (MVP).
_WINTER_SEASONS = frozenset(
    {
        "cool_winter",
        "deep_winter",
        "dark_winter",
        "true_winter",
        "bright_winter",
    }
)

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
    "shorts": ["top", "t-shirt", "shirt", "blouse", "sweater"],
}


def _norm_type(t: str | None) -> str:
    if not t:
        return "other"
    x = t.strip().lower()
    # Normalize common variants
    aliases = {
        "tee": "t-shirt",
        "tshirt": "t-shirt",
        "tank": "t-shirt",
        "tank_top": "t-shirt",
        "camisole": "blouse",
        "cardigan": "sweater",
        "hoodie": "sweater",
        "pullover": "sweater",
        "polo": "shirt",
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
    # Cool / deep / true winter: cool, high contrast
    elif season in _WINTER_SEASONS:
        best = ["black", "white", "navy", "emerald", "ruby", "cobalt", "silver"]
        avoid = ["orange", "warm brown", "camel", "mustard"]
    else:
        best, avoid = [], []

    if any(a in c for a in avoid):
        return 0.0
    if any(b in c for b in best):
        return 1.0
    # neutrals (substring match; include denim / charcoal so tagged colors still score)
    neutrals = [
        "black",
        "white",
        "grey",
        "gray",
        "charcoal",
        "beige",
        "cream",
        "navy",
        "brown",
        "indigo",
        "denim",
        "khaki",
        "stone",
        "slate",
    ]
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


def _type_pairable_wardrobe_count(candidate: dict, wardrobe: list[dict]) -> int:
    """How many wardrobe pieces are the right garment category to pair (ignore formality/pattern)."""
    c_type = _norm_type(candidate.get("type"))
    compatible = set(PAIRING_RULES.get(c_type, []))
    if not compatible:
        return 0
    n = 0
    for w in wardrobe:
        if _norm_type(w.get("type")) in compatible:
            n += 1
    return n


def normalize_outfit_potential(outfits: int, candidate: dict, wardrobe: list[dict]) -> float:
    """
    Map raw pairing count to 0..1. Small digital closets: score vs how many pieces could
    ever pair (type-level), not vs a fixed target of 30. Larger closets: also benefit from
    a softer absolute scale (full credit at ~10 strict pairings).
    """
    eligible = _type_pairable_wardrobe_count(candidate, wardrobe)
    if eligible > 0:
        norm_relative = outfits / float(eligible)
    else:
        norm_relative = 0.0
    norm_absolute = min(outfits / 10.0, 1.0)
    return min(1.0, max(norm_relative, norm_absolute))


def seasonal_versatility(candidate: dict) -> float:
    seasons = candidate.get("seasons") or []
    if not isinstance(seasons, list):
        return 0.5
    n = len({s.strip().lower() for s in seasons if isinstance(s, str) and s.strip()})
    if n == 0:
        # Model often omits seasons; basics are not "zero-season" items.
        if _norm_type(candidate.get("type")) in _YEAR_ROUND_TYPES:
            return 1.0
        return 0.5
    return min(max(n / 4.0, 0.0), 1.0)


def score_candidate(candidate: dict) -> dict:
    """
    Main scoring entrypoint for the API.
    """
    wardrobe = wardrobe_db.list_wardrobe_items()
    color_season = user_profile.get_color_season()

    outfits = outfit_potential(candidate, wardrobe)
    outfit_potential_norm = normalize_outfit_potential(outfits, candidate, wardrobe)
    season_norm = seasonal_versatility(candidate)
    color_norm = _color_match_score(color_season, _norm_color(candidate.get("primary_color")))

    # Weight outfit potential, seasonal versatility, and color match only (sums to 1.0).
    utility = (
        outfit_potential_norm * 0.45
        + season_norm * 0.275
        + color_norm * 0.275
    ) * 100.0

    price = float(candidate.get("price") or 0.0)
    cost_per_wear = round(price / max(outfits, 1), 2) if price else None

    return {
        "score": round(utility, 1),
        "outfit_potential": outfits,
        "outfit_potential_normalized": round(outfit_potential_norm, 2),
        "seasonal_versatility": round(season_norm, 2),
        "color_match": round(color_norm, 2),
        "cost_per_wear": cost_per_wear,
        "color_season": color_season,
    }


# --- Additive API (does not change logic above) --------------------------------

def calculate_outfit_potential(candidate: dict, wardrobe: list[dict]) -> int:
    """Delegate to existing outfit potential; same behavior as before."""
    return outfit_potential(candidate, wardrobe)


def calculate_seasonal_versatility(candidate: dict) -> float:
    """Delegate to existing seasonal versatility."""
    return seasonal_versatility(candidate)


def calculate_color_match(color_season: str | None, item_color: str) -> float:
    """Delegate to existing color match helper."""
    return _color_match_score(color_season, item_color)


def calculate_utility_score(item: dict) -> dict:
    """Same outputs as score_candidate() (used by enhanced scoring)."""
    return score_candidate(item)

