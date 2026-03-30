"""
Tool implementations for outfits ReAct orchestration.
"""
from __future__ import annotations

from typing import Any

from services.utility_score import _formality_ok, _norm_pattern, _norm_type

CONFLICTS: dict[str, set[str]] = {
    "stripes": {"floral", "geometric", "plaid", "polka_dot"},
    "floral": {"stripes", "geometric", "plaid"},
    "geometric": {"floral", "stripes"},
    "plaid": {"floral", "stripes"},
    "polka_dot": {"stripes", "geometric"},
}

SLOT_MAP = {
    "top": "top",
    "t-shirt": "top",
    "shirt": "top",
    "blouse": "top",
    "sweater": "top",
    "hoodie": "top",
    "pullover": "top",
    "tank": "top",
    "cardigan": "layer",
    "vest": "layer",
    "pants": "bottom",
    "jeans": "bottom",
    "skirt": "bottom",
    "shorts": "bottom",
    "leggings": "bottom",
    "dress": "dress",
    "blazer": "layer",
    "jacket": "layer",
    "coat": "layer",
    "shoes": "shoes",
    "boots": "shoes",
    "sneakers": "shoes",
    "sandals": "shoes",
    "heels": "shoes",
    "loafers": "shoes",
    "flats": "shoes",
    "tote": "other",
    "bag": "other",
}


def item_slot(item_type: str | None) -> str:
    return SLOT_MAP.get(_norm_type(item_type), "other")


def pattern_compatible(p1: str | None, p2: str | None) -> bool:
    n1 = _norm_pattern(p1)
    n2 = _norm_pattern(p2)
    if n1 in ("solid", "other", "") or n2 in ("solid", "other", ""):
        return True
    return n2 not in CONFLICTS.get(n1, set())


def formality_compatible(f1: int | None, f2: int | None) -> bool:
    try:
        return _formality_ok(int(f1 or 3), int(f2 or 3))
    except Exception:
        return True


def search_wardrobe(
    wardrobe_items: list[dict[str, Any]],
    *,
    types: list[str] | None = None,
    max_formality_gap: int | None = None,
    candidate_formality: int | None = None,
    seasons: list[str] | None = None,
    colors: list[str] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    type_set = {_norm_type(t) for t in (types or []) if t}
    season_set = {s.strip().lower() for s in (seasons or []) if isinstance(s, str) and s.strip()}
    color_l = [c.strip().lower() for c in (colors or []) if isinstance(c, str) and c.strip()]

    for w in wardrobe_items:
        w_type = _norm_type(w.get("type"))
        if type_set and w_type not in type_set:
            continue

        if max_formality_gap is not None and candidate_formality is not None:
            try:
                wf = int(w.get("formality") or 3)
                if abs(int(candidate_formality) - wf) > int(max_formality_gap):
                    continue
            except Exception:
                pass

        if season_set:
            ws = w.get("seasons") or []
            if isinstance(ws, list):
                ws_norm = {str(s).strip().lower() for s in ws if str(s).strip()}
                if ws_norm and ws_norm.isdisjoint(season_set):
                    continue

        if color_l:
            w_color = str(w.get("primary_color") or "").strip().lower()
            if w_color and not any(c in w_color or w_color in c for c in color_l):
                continue

        out.append(w)
    return out


def check_style_rules(candidate: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    c_form = int(candidate.get("formality") or 3)
    c_pat = candidate.get("pattern")
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for w in items:
        ok_form = formality_compatible(c_form, int(w.get("formality") or 3))
        ok_pat = pattern_compatible(c_pat, w.get("pattern"))
        if ok_form and ok_pat:
            valid.append(w)
        else:
            rejected.append(
                {
                    "id": w.get("id"),
                    "reason": "formality" if not ok_form else "pattern",
                }
            )
    return {"valid_items": valid, "rejected": rejected}


def weather_check(items: list[dict[str, Any]], weather_temp: int | None, weather_conditions: str | None) -> dict[str, Any]:
    temp = weather_temp if isinstance(weather_temp, int) else None
    cond = (weather_conditions or "").strip().lower()
    details: list[dict[str, Any]] = []
    total = 0.0

    for w in items:
        t = _norm_type(w.get("type"))
        mat = str(w.get("material") or "").lower()
        score = 0.6
        if temp is not None:
            if temp <= 45 and t in {"coat", "jacket", "sweater", "blazer"}:
                score += 0.3
            if temp >= 80 and t in {"shorts", "skirt", "t-shirt", "top"}:
                score += 0.25
            if temp >= 80 and t in {"coat", "sweater"}:
                score -= 0.25
            if temp <= 45 and t in {"shorts"}:
                score -= 0.3
        if "rain" in cond and t in {"shoes", "coat", "jacket"}:
            score += 0.1
        if "rain" in cond and ("silk" in mat or "suede" in mat):
            score -= 0.2
        score = max(0.0, min(1.0, score))
        total += score
        details.append({"id": w.get("id"), "weather_score": round(score, 2)})

    avg = round(total / max(len(items), 1), 2) if items else 0.5
    return {"weather_score": avg, "details": details}


def trend_check(
    items: list[dict[str, Any]],
    trends: list[dict[str, Any]] | None,
    color_season: str | None,
) -> dict[str, Any]:
    trend_rows = trends or []
    if not trend_rows:
        return {"trend_score": 0.5, "reason": "no trend data"}

    dominant_pool: list[str] = []
    for t in trend_rows[:20]:
        colors = t.get("dominant_colors") or []
        for c in colors:
            if isinstance(c, str) and c.strip():
                dominant_pool.append(c.strip().lower())
    if not dominant_pool:
        return {"trend_score": 0.5, "reason": "trend rows had no colors"}

    match = 0
    for it in items:
        pc = str(it.get("primary_color") or "").strip().lower()
        if pc and any(pc in c or c in pc for c in dominant_pool):
            match += 1
    color_match = match / max(len(items), 1) if items else 0.0

    season_bonus = 0.0
    if color_season:
        s = color_season.lower()
        if "winter" in s:
            winter_hits = sum(1 for c in dominant_pool if c in {"black", "white", "navy", "charcoal", "ruby"})
            season_bonus = min(0.2, winter_hits / 25.0)
        elif "spring" in s:
            spring_hits = sum(1 for c in dominant_pool if c in {"coral", "peach", "aqua", "turquoise"})
            season_bonus = min(0.2, spring_hits / 25.0)
    score = round(max(0.0, min(1.0, color_match * 0.8 + 0.2 + season_bonus)), 2)
    return {"trend_score": score, "reason": "dominant-color overlap with trends"}

