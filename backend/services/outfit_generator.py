"""
Outfit generation MVP (rules-based + scoring).

Inputs: candidate item attributes + occasion/weather/vibe.
Uses: user's saved wardrobe + color season.

Output: 4 outfit cards with item IDs from wardrobe + reasoning and scores.
Later: we can add LLM reasoning / ReAct agent.
"""

from __future__ import annotations

from typing import Any

from services.utility_score import (
    PAIRING_RULES,
    _color_match_score,
    _formality_ok,
    _norm_pattern,
    _norm_type,
    seasonal_versatility,
)
from services import wardrobe_db, user_profile


def _pick_color(input_color: str | None) -> str:
    return (input_color or "").strip().lower()


def _candidate_formality(candidate: dict[str, Any]) -> int:
    try:
        return int(candidate.get("formality") or 3)
    except Exception:
        return 3


def _candidate_pattern(candidate: dict[str, Any]) -> str:
    return _norm_pattern(candidate.get("pattern"))


def _style_coherence_ok(candidate: dict[str, Any], wardrobe_item: dict[str, Any]) -> float:
    """
    Convert rule checks into a 0..1 coherence signal.
    """
    c_form = _candidate_formality(candidate)
    w_form = int(wardrobe_item.get("formality") or 3)
    form_ok = _formality_ok(c_form, w_form)

    c_pat = _candidate_pattern(candidate)
    w_pat = _norm_pattern(wardrobe_item.get("pattern"))
    pat_ok = c_pat == "solid" or w_pat == "solid" or (c_pat != "other" and w_pat != "other")

    # Since our MVP already filters by type, coherence here focuses on formality/pattern.
    return 1.0 if (form_ok and pat_ok) else 0.6 if (form_ok or pat_ok) else 0.2


def generate_outfits(payload: dict[str, Any]) -> dict[str, Any]:
    occasion = str(payload.get("occasion") or "").strip()
    vibe = str(payload.get("vibe") or "").strip()
    candidate: dict[str, Any] = payload.get("candidate") or {}

    wardrobe_items = wardrobe_db.list_wardrobe_items()
    color_season = user_profile.get_color_season()

    candidate_type = _norm_type(candidate.get("type"))
    compatible = set(PAIRING_RULES.get(candidate_type, []))

    c_form = _candidate_formality(candidate)
    c_pat = _candidate_pattern(candidate)

    def _is_compatible(w: dict[str, Any]) -> bool:
        w_type = _norm_type(w.get("type"))
        if compatible and w_type not in compatible:
            return False
        w_form = int(w.get("formality") or 3)
        if not _formality_ok(c_form, w_form):
            return False
        w_pat = _norm_pattern(w.get("pattern"))
        # Prefer solid compatibility; otherwise allow anything but clearly clashing patterns.
        if not (c_pat == "solid" or w_pat == "solid"):
            # Minimal conflict detection for MVP.
            conflicts = {
                "stripes": {"floral", "geometric", "plaid", "polka_dot"},
                "floral": {"stripes", "geometric", "plaid"},
                "geometric": {"floral", "stripes"},
                "plaid": {"floral", "stripes"},
                "polka_dot": {"stripes", "geometric"},
            }
            if w_pat in conflicts.get(c_pat, set()):
                return False
        return True

    # If compatible types empty (unknown candidate type), allow any wardrobe item.
    if not compatible:
        compatible_items = wardrobe_items
    else:
        compatible_items = [w for w in wardrobe_items if _norm_type(w.get("type")) in compatible]

    filtered = [w for w in compatible_items if _is_compatible(w)]

    def _rank(w: dict[str, Any]) -> float:
        c_color = _color_match_score(color_season, _pick_color(candidate.get("primary_color")))
        w_color = _color_match_score(color_season, _pick_color(w.get("primary_color")))
        c_season = seasonal_versatility(candidate)
        coherence = _style_coherence_ok(candidate, w)
        return (
            c_color * 0.25
            + w_color * 0.40
            + c_season * 0.15
            + coherence * 0.20
        )

    scored = sorted(filtered, key=_rank, reverse=True)
    if len(scored) < 4:
        # Fallback: if filtering is too strict, rank a broader set by color/season.
        broader = compatible_items or wardrobe_items
        scored = sorted(broader, key=_rank, reverse=True)

    fallback_used = False
    top = scored[:4]
    if len(scored) < 4:
        fallback_used = True

    outfits: list[dict[str, Any]] = []
    for w in top:
        w_color = _color_match_score(color_season, _pick_color(w.get("primary_color")))
        c_color = _color_match_score(color_season, _pick_color(candidate.get("primary_color")))
        c_season = seasonal_versatility(candidate)
        coherence = _style_coherence_ok(candidate, w)

        overall = round(
            (c_color * 0.25 + w_color * 0.40 + c_season * 0.15 + coherence * 0.20) * 100,
            1,
        )

        reasoning_bits: list[str] = []
        if occasion:
            reasoning_bits.append(f"fits the requested occasion ({occasion})")
        if vibe:
            reasoning_bits.append(f"matches the vibe ({vibe})")
        reasoning_bits.append(f"formality compatibility (±2) with your wardrobe")
        reasoning_bits.append("pattern and silhouette work together")
        if color_season:
            reasoning_bits.append(f"color harmony with your {color_season.replace('_', ' ')} palette")
        else:
            reasoning_bits.append("color harmony based on your wardrobe neutral compatibility")

        outfits.append(
            {
                "items": [w.get("id")],
                "reasoning": "; ".join(reasoning_bits),
                "scores": {
                    "color_match": round((c_color * 0.5 + w_color * 0.5), 2),
                    "seasonal_versatility": round(c_season, 2),
                    "style_coherence": round(coherence, 2),
                },
                "overall_score": overall,
                "matched_item": {
                    "id": w.get("id"),
                    "image_url": w.get("image_url"),
                    "type": w.get("type"),
                    "primary_color": w.get("primary_color"),
                    "pattern": w.get("pattern"),
                    "formality": w.get("formality"),
                },
            }
        )

    return {
        "outfits": outfits,
        "candidate": candidate,
        "color_season": color_season,
        "debug": {
            "candidate_type": candidate_type,
            "compatible_expected_types": sorted(list(compatible)) if compatible else [],
            "compatible_items_count": len(compatible_items),
            "filtered_count": len(filtered),
            "fallback_used": fallback_used,
        },
    }


