"""
Outfit generation service:
- rules-based baseline
- optional ReAct tool orchestration
- optional LLM-as-a-judge
- weather/trend-aware multi-item outfits
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

# PRD-style utility blend: color + seasonal + coherence (outfit potential) weighted strongly;
# judge blend favors qualitative assessment slightly more than raw heuristics.
_ANCHOR_W = {"c_color": 0.22, "w_color": 0.28, "c_season": 0.18, "coherence": 0.32}
# Sums to 0.92; remaining 0.08 is slot-completeness (PRD “wardrobe coverage / outfit completeness”).
_PREJUDGE_W = {
    "color_avg": 0.20,
    "season": 0.16,
    "coherence": 0.26,
    "weather": 0.15,
    "trend": 0.15,
}
_JUDGE_BLEND = 0.35
_COMPLETENESS_WEIGHT = 0.08
from services import trends_db, user_profile, wardrobe_db
from services.outfit_judge import judge_outfit
from services.outfit_react_agent import run_llm_outfit_recommender, run_react_outfit_planner
from services.outfit_tools import formality_compatible, item_slot, pattern_compatible, trend_check, weather_check


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
    pat_ok = pattern_compatible(c_pat, w_pat)

    # Since our MVP already filters by type, coherence here focuses on formality/pattern.
    return 1.0 if (form_ok and pat_ok) else 0.6 if (form_ok or pat_ok) else 0.2


def _is_pair_compatible(candidate: dict[str, Any], w: dict[str, Any], compatible: set[str]) -> bool:
    c_form = _candidate_formality(candidate)
    c_pat = _candidate_pattern(candidate)
    w_type = _norm_type(w.get("type"))
    if compatible and w_type not in compatible:
        return False
    w_form = int(w.get("formality") or 3)
    if not _formality_ok(c_form, w_form):
        return False
    if not pattern_compatible(c_pat, _norm_pattern(w.get("pattern"))):
        return False
    return True


def _rank_anchor(
    candidate: dict[str, Any],
    anchor: dict[str, Any],
    color_season: str | None,
) -> float:
    c_color = _color_match_score(color_season, _pick_color(candidate.get("primary_color")))
    w_color = _color_match_score(color_season, _pick_color(anchor.get("primary_color")))
    c_season = seasonal_versatility(candidate)
    coherence = _style_coherence_ok(candidate, anchor)
    return (
        c_color * _ANCHOR_W["c_color"]
        + w_color * _ANCHOR_W["w_color"]
        + c_season * _ANCHOR_W["c_season"]
        + coherence * _ANCHOR_W["coherence"]
    )


def _occasion_vibe_text(occasion: str, vibe: str) -> str:
    return " ".join(p for p in (occasion, vibe) if p).lower()


def _occasion_flags(occasion: str, vibe: str) -> dict[str, bool]:
    t = _occasion_vibe_text(occasion, vibe)
    return {
        "formal_plus": any(
            k in t for k in ("wedding", "gala", "formal", "black tie", "cocktail", "ceremony")
        ),
        "business": any(
            k in t for k in ("business", "client", "office", "meeting", "interview", "work", "presentation")
        ),
        "athletic": any(k in t for k in ("gym", "workout", "run", "yoga", "sport", "training", "hike")),
        "beach": any(k in t for k in ("beach", "pool", "resort")),
        "party": any(k in t for k in ("party", "club", "night out", "date", "concert")),
    }


def _weather_bucket(temp: int | None, conditions: str | None) -> str:
    cond = (conditions or "").lower()
    if "rain" in cond or "storm" in cond or "drizzle" in cond:
        return "rain"
    if temp is None:
        return "mild"
    if temp <= 40:
        return "cold"
    if temp <= 55:
        return "cool"
    if temp <= 72:
        return "mild"
    if temp <= 82:
        return "warm"
    return "hot"


def _slot_plan(candidate_slot: str, flags: dict[str, bool], wb: str) -> list[str]:
    if flags["athletic"]:
        if candidate_slot == "dress":
            return ["shoes"]
        if candidate_slot == "top":
            return ["bottom", "shoes"]
        if candidate_slot == "bottom":
            return ["top", "shoes"]
        return ["top", "bottom", "shoes"]

    if candidate_slot == "dress":
        out: list[str] = []
        if wb in {"cold", "cool", "rain"} or flags["formal_plus"] or flags["business"]:
            out.append("layer")
        out.append("shoes")
        return out

    if candidate_slot == "top":
        wanted = ["bottom", "shoes"]
        skip_layer = wb == "hot" and not flags["business"] and not flags["formal_plus"]
        if not skip_layer:
            wanted.insert(1, "layer")
        return wanted

    if candidate_slot == "bottom":
        wanted = ["top", "shoes"]
        skip_layer = wb == "hot" and not flags["business"] and not flags["formal_plus"]
        if not skip_layer:
            wanted.insert(1, "layer")
        return wanted

    return ["top", "bottom", "layer", "shoes"]


def _slot_fill_score(
    w: dict[str, Any],
    *,
    candidate: dict[str, Any],
    anchor: dict[str, Any],
    color_season: str | None,
    slot: str,
    wb: str,
    flags: dict[str, bool],
) -> float:
    c_color = _color_match_score(color_season, _pick_color(w.get("primary_color")))
    a_color = _color_match_score(color_season, _pick_color(anchor.get("primary_color")))
    coh = _style_coherence_ok(candidate, w)
    w_season = seasonal_versatility(w)
    score = c_color * 0.32 + a_color * 0.24 + coh * 0.28 + w_season * 0.16

    wt = _norm_type(w.get("type"))
    if wb in {"cold", "cool"} and wt in {"coat", "jacket", "sweater", "blazer", "cardigan"}:
        score += 0.07
    if wb == "hot" and wt in {"shorts", "skirt", "t-shirt", "tank", "sandals"}:
        score += 0.06
    if wb == "rain" and wt in {"coat", "jacket", "boots", "shoes"}:
        score += 0.05
    if flags["business"] and slot == "layer" and wt == "blazer":
        score += 0.11
    if flags["formal_plus"] and slot == "layer" and wt in {"blazer", "coat"}:
        score += 0.09
    if flags["beach"] and wt in {"shorts", "sandals", "skirt"}:
        score += 0.06
    if (flags["formal_plus"] or flags["business"]) and wt == "shorts":
        score -= 0.22
    if wb in {"cold", "cool", "rain"} and wt == "shorts":
        score -= 0.12
    if flags["athletic"] and wt in {"shorts", "leggings", "sneakers", "t-shirt", "tank"}:
        score += 0.06

    return score


def _compose_outfit_items(
    candidate: dict[str, Any],
    anchor: dict[str, Any],
    wardrobe_items: list[dict[str, Any]],
    *,
    occasion: str = "",
    vibe: str = "",
    weather_temp: int | None = None,
    weather_conditions: str | None = None,
    color_season: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    c_slot = item_slot(candidate.get("type"))
    used_ids = {str(anchor.get("id"))}
    outfit = [anchor]
    flags = _occasion_flags(occasion, vibe)
    wb = _weather_bucket(weather_temp, weather_conditions)
    wanted = _slot_plan(c_slot, flags, wb)

    for slot in wanted:
        best: dict[str, Any] | None = None
        best_s = -1.0
        for w in wardrobe_items:
            wid = str(w.get("id"))
            if wid in used_ids:
                continue
            if item_slot(w.get("type")) != slot:
                continue
            if not formality_compatible(candidate.get("formality"), w.get("formality")):
                continue
            if not pattern_compatible(candidate.get("pattern"), w.get("pattern")):
                continue
            s = _slot_fill_score(
                w,
                candidate=candidate,
                anchor=anchor,
                color_season=color_season,
                slot=slot,
                wb=wb,
                flags=flags,
            )
            if s > best_s:
                best_s = s
                best = w
        if best:
            outfit.append(best)
            used_ids.add(str(best.get("id")))
    return outfit, wanted


def _explain_bits(
    *,
    occasion: str,
    vibe: str,
    color_season: str | None,
    weather_score: float,
    trend_score: float,
) -> list[str]:
    bits: list[str] = []
    if occasion:
        bits.append(f"fits the requested occasion ({occasion})")
    if vibe:
        bits.append(f"matches the vibe ({vibe})")
    bits.append("formality and pattern compatibility across pieces")
    bits.append(f"weather suitability score {round(weather_score * 100)}%")
    bits.append(f"trend relevance score {round(trend_score * 100)}%")
    if color_season:
        bits.append(f"color harmony with your {color_season.replace('_', ' ')} palette")
    return bits


async def generate_outfits(payload: dict[str, Any]) -> dict[str, Any]:
    occasion = str(payload.get("occasion") or "").strip()
    vibe = str(payload.get("vibe") or "").strip()
    weather_temp_raw = payload.get("weather_temp")
    weather_temp = int(weather_temp_raw) if isinstance(weather_temp_raw, int) else None
    weather_conditions = str(payload.get("weather_conditions") or "").strip() or None
    engine = str(payload.get("engine") or "").strip().lower() or "rules"
    candidate: dict[str, Any] = payload.get("candidate") or {}

    wardrobe_items = wardrobe_db.list_wardrobe_items()
    color_season = user_profile.get_color_season()
    trends = trends_db.get_trends_for_user(limit=10)

    candidate_type = _norm_type(candidate.get("type"))
    compatible = set(PAIRING_RULES.get(candidate_type, []))

    # If compatible types empty (unknown candidate type), allow any wardrobe item.
    if not compatible:
        compatible_items = wardrobe_items
    else:
        compatible_items = [w for w in wardrobe_items if _norm_type(w.get("type")) in compatible]

    filtered = [w for w in compatible_items if _is_pair_compatible(candidate, w, compatible)]
    scored = sorted(filtered, key=lambda w: _rank_anchor(candidate, w, color_season), reverse=True)
    react_trace: list[dict[str, Any]] = []
    selected_pool = scored
    engine_used = "rules"
    react_fallback_reason: str | None = None
    if engine == "react":
        llm_out = await run_llm_outfit_recommender(
            candidate=candidate,
            wardrobe_items=wardrobe_items,
            color_season=color_season,
            occasion=occasion,
            vibe=vibe,
            weather_temp=weather_temp,
            weather_conditions=weather_conditions,
        )
        if llm_out.get("success"):
            item_by_id = {str(w.get("id")): w for w in wardrobe_items if w.get("id") is not None}
            outfits: list[dict[str, Any]] = []
            for plan in llm_out.get("outfits", []):
                ids = [str(i) for i in plan.get("item_ids", [])]
                chosen = [item_by_id[i] for i in ids if i in item_by_id]
                if len(chosen) < 2:
                    continue
                anchor = chosen[0]
                w_color = _color_match_score(color_season, _pick_color(anchor.get("primary_color")))
                c_color = _color_match_score(color_season, _pick_color(candidate.get("primary_color")))
                c_season = seasonal_versatility(candidate)
                coherence_vals = [_style_coherence_ok(candidate, it) for it in chosen]
                coherence = sum(coherence_vals) / max(len(coherence_vals), 1)
                wcheck = weather_check(chosen, weather_temp, weather_conditions)
                tcheck = trend_check(chosen, trends, color_season)
                weather_score = float(wcheck.get("weather_score") or 0.5)
                trend_score = float(tcheck.get("trend_score") or 0.5)
                overall_prejudge = (
                    ((c_color + w_color) * 0.5) * _PREJUDGE_W["color_avg"]
                    + c_season * _PREJUDGE_W["season"]
                    + coherence * _PREJUDGE_W["coherence"]
                    + weather_score * _PREJUDGE_W["weather"]
                    + trend_score * _PREJUDGE_W["trend"]
                    + _COMPLETENESS_WEIGHT
                )
                judge = await judge_outfit(
                    outfit_items=[candidate] + chosen,
                    occasion=occasion,
                    vibe=vibe,
                    weather_temp=weather_temp,
                    weather_conditions=weather_conditions,
                    color_season=color_season,
                    trend_context=str([t.get("name") for t in trends[:5]]),
                )
                judge_overall_norm = max(0.0, min(1.0, float(judge.get("overall_score", 6.0)) / 10.0))
                prejudge_share = 1.0 - _JUDGE_BLEND
                overall = round(
                    (overall_prejudge * prejudge_share + judge_overall_norm * _JUDGE_BLEND) * 100,
                    1,
                )
                reasoning_bits = _explain_bits(
                    occasion=occasion,
                    vibe=vibe,
                    color_season=color_season,
                    weather_score=weather_score,
                    trend_score=trend_score,
                )
                if str(plan.get("reasoning") or "").strip():
                    reasoning_bits.insert(0, str(plan.get("reasoning")).strip())
                reasoning_bits.append(
                    f"judge overall {judge.get('overall_score', 6.0)}/10 based on coherence, color, occasion, trend, practicality"
                )
                outfits.append(
                    {
                        "items": [it.get("id") for it in chosen if it.get("id") is not None],
                        "item_details": [
                            {
                                "id": it.get("id"),
                                "type": it.get("type"),
                                "image_url": it.get("image_url"),
                                "primary_color": it.get("primary_color"),
                                "pattern": it.get("pattern"),
                                "formality": it.get("formality"),
                            }
                            for it in chosen
                        ],
                        "reasoning": "; ".join(reasoning_bits),
                        "scores": {
                            "color_match": round((c_color * 0.5 + w_color * 0.5), 2),
                            "seasonal_versatility": round(c_season, 2),
                            "style_coherence": round(coherence, 2),
                            "weather_fit": round(weather_score, 2),
                            "trend_relevance": round(trend_score, 2),
                            "judge": judge,
                        },
                        "overall_score": overall,
                        "matched_item": {
                            "id": anchor.get("id"),
                            "image_url": anchor.get("image_url"),
                            "type": anchor.get("type"),
                            "primary_color": anchor.get("primary_color"),
                            "pattern": anchor.get("pattern"),
                            "formality": anchor.get("formality"),
                        },
                    }
                )
            if outfits:
                outfits.sort(key=lambda x: float(x.get("overall_score") or 0), reverse=True)
                return {
                    "outfits": outfits[:4],
                    "candidate": candidate,
                    "color_season": color_season,
                    "debug": {
                        "engine": "react",
                        "candidate_type": candidate_type,
                        "compatible_expected_types": sorted(list(compatible)) if compatible else [],
                        "compatible_items_count": len(compatible_items),
                        "filtered_count": len(filtered),
                        "fallback_used": False,
                        "trace": [],
                        "react_fallback_reason": None,
                        "llm_mode": "direct_outfit_generation",
                    },
                }
        # LLM-only contract: do not silently drop back to deterministic rules.
        reason = str(llm_out.get("reason") or "llm_no_outfits")
        raise RuntimeError(f"LLM recommender unavailable: {reason}")

        react_out = await run_react_outfit_planner(
            candidate=candidate,
            wardrobe_items=wardrobe_items,
            color_season=color_season,
            occasion=occasion,
            vibe=vibe,
            weather_temp=weather_temp,
            weather_conditions=weather_conditions,
        )
        react_trace = react_out.get("trace") or []
        rid_set = {str(i) for i in react_out.get("selected_item_ids", [])}
        if rid_set:
            selected_pool = [w for w in wardrobe_items if str(w.get("id")) in rid_set]
            selected_pool = sorted(selected_pool, key=lambda w: _rank_anchor(candidate, w, color_season), reverse=True)
            engine_used = "react"
        else:
            react_fallback_reason = react_fallback_reason or "react returned empty selected_item_ids"

    if len(selected_pool) < 4:
        # Fallback: if filtering is too strict, rank a broader set by color/season.
        broader = compatible_items or wardrobe_items
        selected_pool = sorted(broader, key=lambda w: _rank_anchor(candidate, w, color_season), reverse=True)

    fallback_used = False
    top = selected_pool[:4]
    if len(selected_pool) < 4:
        fallback_used = True

    outfits: list[dict[str, Any]] = []
    for w in top:
        outfit_items, slot_plan = _compose_outfit_items(
            candidate,
            w,
            wardrobe_items,
            occasion=occasion,
            vibe=vibe,
            weather_temp=weather_temp,
            weather_conditions=weather_conditions,
            color_season=color_season,
        )
        w_color = _color_match_score(color_season, _pick_color(w.get("primary_color")))
        c_color = _color_match_score(color_season, _pick_color(candidate.get("primary_color")))
        color_avg = (c_color + w_color) * 0.5
        c_season = seasonal_versatility(candidate)
        coherence = _style_coherence_ok(candidate, w)
        wcheck = weather_check(outfit_items, weather_temp, weather_conditions)
        tcheck = trend_check(outfit_items, trends, color_season)
        weather_score = float(wcheck.get("weather_score") or 0.5)
        trend_score = float(tcheck.get("trend_score") or 0.5)

        fills = max(len(outfit_items) - 1, 0)
        expected = max(len(slot_plan), 1)
        completeness = min(1.0, fills / expected)

        pw = _PREJUDGE_W
        overall_prejudge = (
            color_avg * pw["color_avg"]
            + c_season * pw["season"]
            + coherence * pw["coherence"]
            + weather_score * pw["weather"]
            + trend_score * pw["trend"]
            + completeness * _COMPLETENESS_WEIGHT
        )
        judge = await judge_outfit(
            outfit_items=[candidate] + outfit_items,
            occasion=occasion,
            vibe=vibe,
            weather_temp=weather_temp,
            weather_conditions=weather_conditions,
            color_season=color_season,
            trend_context=str([t.get("name") for t in trends[:5]]),
        )
        judge_overall_norm = max(0.0, min(1.0, float(judge.get("overall_score", 6.0)) / 10.0))
        prejudge_share = 1.0 - _JUDGE_BLEND
        overall = round(
            (overall_prejudge * prejudge_share + judge_overall_norm * _JUDGE_BLEND) * 100,
            1,
        )

        reasoning_bits = _explain_bits(
            occasion=occasion,
            vibe=vibe,
            color_season=color_season,
            weather_score=weather_score,
            trend_score=trend_score,
        )
        reasoning_bits.append(
            f"judge overall {judge.get('overall_score', 6.0)}/10 based on coherence, color, occasion, trend, practicality"
        )

        outfits.append(
            {
                "items": [it.get("id") for it in outfit_items if it.get("id") is not None],
                "item_details": [
                    {
                        "id": it.get("id"),
                        "type": it.get("type"),
                        "image_url": it.get("image_url"),
                        "primary_color": it.get("primary_color"),
                        "pattern": it.get("pattern"),
                        "formality": it.get("formality"),
                    }
                    for it in outfit_items
                ],
                "reasoning": "; ".join(reasoning_bits),
                "scores": {
                    "color_match": round((c_color * 0.5 + w_color * 0.5), 2),
                    "seasonal_versatility": round(c_season, 2),
                    "style_coherence": round(coherence, 2),
                    "weather_fit": round(weather_score, 2),
                    "trend_relevance": round(trend_score, 2),
                    "judge": judge,
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
            "engine": engine_used,
            "candidate_type": candidate_type,
            "compatible_expected_types": sorted(list(compatible)) if compatible else [],
            "compatible_items_count": len(compatible_items),
            "filtered_count": len(filtered),
            "fallback_used": fallback_used,
            "trace": react_trace,
            "react_fallback_reason": react_fallback_reason,
        },
    }


