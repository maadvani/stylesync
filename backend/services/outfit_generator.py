"""
Outfit generation: structured top + bottom + shoes (+ optional layer), up to four looks with
disjoint tops/bottoms (shoes may repeat), LLM-as-a-judge for scores.
Legacy slot-composer helpers remain for ReAct tooling elsewhere.
"""

from __future__ import annotations

from typing import Any

from services.utility_score import (
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
from services.outfit_react_agent import run_llm_outfit_recommender
from services.tracing import traceable
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
        # Park / picnic / BBQ: avoid pushing blazers and coats when weather is already comfortable.
        "casual_outdoor": any(
            k in t
            for k in (
                "picnic",
                "bbq",
                "barbecue",
                "park",
                "fair",
                "festival",
                "camping",
                "backyard",
                "outdoor brunch",
            )
        ),
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
        skip_layer = (flags["casual_outdoor"] and wb in {"mild", "warm", "hot"}) or (
            wb in {"hot", "warm"} and not flags["business"] and not flags["formal_plus"]
        )
        if not skip_layer:
            wanted.insert(1, "layer")
        return wanted

    if candidate_slot == "bottom":
        wanted = ["top", "shoes"]
        skip_layer = (flags["casual_outdoor"] and wb in {"mild", "warm", "hot"}) or (
            wb in {"hot", "warm"} and not flags["business"] and not flags["formal_plus"]
        )
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
    exclude_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    c_slot = item_slot(candidate.get("type"))
    used_ids = {str(anchor.get("id"))}
    outfit = [anchor]
    flags = _occasion_flags(occasion, vibe)
    wb = _weather_bucket(weather_temp, weather_conditions)
    wanted = _slot_plan(c_slot, flags, wb)

    blocked = exclude_ids or set()
    anchor_id = str(anchor.get("id") or "")
    for slot in wanted:
        best: dict[str, Any] | None = None
        best_s = -1.0
        for w in wardrobe_items:
            wid = str(w.get("id"))
            if wid in used_ids:
                continue
            if wid in blocked and wid != anchor_id:
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


def _short_reason(text: Any, fallback: str) -> str:
    s = str(text or "").strip()
    if not s:
        return fallback
    # Keep UI copy concise and avoid trailing punctuation noise from model output.
    s = s.replace("\n", " ").strip().rstrip(" .;")
    return s or fallback


def _piece_phrase(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for it in items:
        t = str(it.get("type") or "").strip().lower()
        c = str(it.get("primary_color") or "").strip().lower()
        if not t:
            continue
        if c:
            parts.append(f"{c} {t}")
        else:
            parts.append(t)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    uniq = [p for p in parts if not (p in seen or seen.add(p))]
    return ", ".join(uniq[:4]) if uniq else "selected pieces"


def _compose_reasoning_text(
    *,
    outfit_items: list[dict[str, Any]],
    judge: dict[str, Any],
    generation_path: str,
    occasion: str,
    vibe: str,
    color_season: str | None,
    weather_score: float,
    trend_score: float,
) -> str:
    desc = str(judge.get("descriptive_reasoning") or "").strip()
    accessories = judge.get("accessory_suggestions") or []
    desc_clean = desc.rstrip(" .;")
    acc_list = [str(x).strip().rstrip(" .;") for x in accessories if str(x).strip()]
    if desc:
        base = f"{desc_clean}." if desc_clean else ""
        if acc_list:
            return f"{base} Accessories: {', '.join(acc_list[:3])}."
        return base

    pieces = _piece_phrase(outfit_items)
    mode_lead = (
        "Chosen by the LLM from your wardrobe for this request."
        if generation_path == "react_primary"
        else "Built from a structured top + bottom + shoes composition."
    )
    occasion_reason = _short_reason(
        (judge.get("occasion_appropriateness") or {}).get("reasoning"),
        "The formality and silhouettes fit the requested plan.",
    )
    practical_reason = _short_reason(
        (judge.get("practicality") or {}).get("reasoning"),
        "The combination remains practical for the weather and day-to-day use.",
    )
    color_reason = _short_reason(
        (judge.get("color_harmony") or {}).get("reasoning"),
        "Colors stay reasonably harmonious across the selected items.",
    )
    style_reason = _short_reason(
        (judge.get("style_coherence") or {}).get("reasoning"),
        "Patterns and formality levels stay coherent together.",
    )
    trend_reason = _short_reason(
        (judge.get("trend_relevance") or {}).get("reasoning"),
        "The look has moderate trend alignment without sacrificing practicality.",
    )
    context_bits: list[str] = []
    if occasion:
        context_bits.append(f"occasion: {occasion}")
    if vibe:
        context_bits.append(f"vibe: {vibe}")
    if color_season:
        context_bits.append(f"palette: {color_season.replace('_', ' ')}")
    context = ", ".join(context_bits)
    overall = float(judge.get("overall_score") or 6.0)
    return (
        f"{mode_lead} Selected pieces: {pieces}. "
        f"{occasion_reason} {style_reason} {color_reason} {practical_reason} {trend_reason} "
        f"(weather fit {round(weather_score * 100)}%, trend relevance {round(trend_score * 100)}%, "
        f"judge {overall:.1f}/10"
        + (f", {context}" if context else "")
        + ")."
    )


def _parse_weather_temp(raw: Any) -> int | None:
    """Accept int/float/str from JSON/API; ignore bools and bad values."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(round(raw))
    try:
        return int(float(str(raw).strip()))
    except Exception:
        return None


def _is_hypothetical_item_id(iid: Any) -> bool:
    s = str(iid or "")
    return s == "hypothetical" or s.startswith("hypothetical::")


def _neutral_rank_candidate() -> dict[str, Any]:
    return {
        "type": "top",
        "formality": 3,
        "pattern": "solid",
        "primary_color": None,
        "seasons": ["spring", "summer", "fall", "winter"],
    }


def _hypothetical_item_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "hypothetical",
        "image_url": candidate.get("image_url") or None,
        "type": candidate.get("type"),
        "primary_color": candidate.get("primary_color"),
        "pattern": candidate.get("pattern"),
        "formality": candidate.get("formality"),
        "material": candidate.get("material"),
    }


def _inject_hypothetical_into_row(
    row: list[dict[str, Any]],
    *,
    hyp: dict[str, Any] | None,
    c_slot: str,
) -> list[dict[str, Any]]:
    """
    Ensure the hypothetical piece is visible in outfit rows when enabled.
    For top/bottom/shoes candidate types, replace the first item in the same slot.
    """
    if hyp is None or c_slot not in {"top", "bottom", "shoes"}:
        return row
    out = list(row)
    for idx, it in enumerate(out):
        if item_slot(it.get("type")) == c_slot:
            out[idx] = hyp
            return out
    # If the slot is unexpectedly missing, prepend hypothetical so it's still visible.
    return [hyp, *out]


def _unique_slot_ids(rows: list[list[dict[str, Any]]], slot_name: str) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for it in row:
            if item_slot(it.get("type")) != slot_name:
                continue
            sid = str(it.get("id") or "")
            if sid and not _is_hypothetical_item_id(sid):
                out.add(sid)
    return out


def _real_ids_in_triplet(row: list[dict[str, Any]]) -> set[str]:
    return {str(x["id"]) for x in row if x.get("id") and not _is_hypothetical_item_id(x.get("id"))}


def _real_ids_disjoint_across_outfits(row: list[dict[str, Any]]) -> set[str]:
    """Top + bottom must stay unique across looks; shoes may repeat (user preference / small closets)."""
    out: set[str] = set()
    for x in row:
        if _is_hypothetical_item_id(x.get("id")):
            continue
        lid = str(x.get("id") or "")
        if not lid:
            continue
        if item_slot(x.get("type")) in {"top", "bottom"}:
            out.add(lid)
    return out


def _triplet_disjoint_ids_valid(row: list[dict[str, Any]]) -> bool:
    if len(row) != 3:
        return False
    rid = _real_ids_in_triplet(row)
    reals = [x for x in row if not _is_hypothetical_item_id(x.get("id"))]
    return len(rid) == len(reals)


def _iter_triplets(
    tops: list[dict[str, Any]],
    bottoms: list[dict[str, Any]],
    shoes: list[dict[str, Any]],
    *,
    hyp: dict[str, Any] | None,
    c_slot: str,
    cap: int = 7,
) -> list[list[dict[str, Any]]]:
    tu, bu, su = tops[:cap], bottoms[:cap], shoes[:cap]
    out: list[list[dict[str, Any]]] = []
    if hyp is not None and c_slot == "top":
        for b in bu:
            for s in su:
                out.append([hyp, b, s])
    elif hyp is not None and c_slot == "bottom":
        for t in tu:
            for s in su:
                out.append([t, hyp, s])
    elif hyp is not None and c_slot == "shoes":
        for t in tu:
            for b in bu:
                out.append([t, b, hyp])
    else:
        for t in tu:
            for b in bu:
                for s in su:
                    out.append([t, b, s])
    return out


@traceable(name="outfits.structured.dfs_disjoint_rows", run_type="chain", tags=["outfits", "structured"])
def _dfs_best_disjoint_rows(
    triplets: list[list[dict[str, Any]]],
    *,
    max_outfits: int = 4,
    cap_triplets: int = 72,
    max_rec_calls: int = 25000,
) -> list[list[dict[str, Any]]]:
    """Backtracking: find up to max_outfits pairwise-disjoint triplets (greedy can miss a 4th valid set)."""
    triplets = [r for r in triplets[:cap_triplets] if _triplet_disjoint_ids_valid(r)]
    best: list[list[dict[str, Any]]] = []
    calls = [0]

    def rec(chosen: list[list[dict[str, Any]]], used: set[str]) -> None:
        nonlocal best
        calls[0] += 1
        if calls[0] > max_rec_calls:
            return
        if len(chosen) > len(best):
            best = [list(r) for r in chosen]
        if len(chosen) >= max_outfits:
            return
        for row in triplets:
            ids = _real_ids_disjoint_across_outfits(row)
            if ids & used:
                continue
            chosen.append(row)
            rec(chosen, used | ids)
            chosen.pop()

    rec([], set())
    return best


@traceable(name="outfits.structured.reuse_fill", run_type="chain", tags=["outfits", "structured"])
def _ensure_four_rows_with_reuse(
    rows: list[list[dict[str, Any]]], triplets: list[list[dict[str, Any]]], *, target: int = 4
) -> tuple[list[list[dict[str, Any]]], bool]:
    """
    Fill to `target` outfits when wardrobe is small by allowing controlled reuse.
    Preference order:
    1) maximize unseen top/bottom IDs,
    2) then maximize unseen shoe IDs,
    3) then avoid exact duplicate triplets when possible.
    """
    if len(rows) >= target or not triplets:
        return rows, False

    picked = [list(r) for r in rows]
    used_top_bottom: set[str] = set()
    used_shoes: set[str] = set()
    seen_triplets: set[tuple[str, str, str]] = set()

    def key_for(row: list[dict[str, Any]]) -> tuple[str, str, str]:
        ids = [str(x.get("id") or "") for x in row[:3]]
        while len(ids) < 3:
            ids.append("")
        return (ids[0], ids[1], ids[2])

    def slot_signature(row: list[dict[str, Any]]) -> tuple[str, str, str]:
        out = {"top": "", "bottom": "", "shoes": ""}
        for x in row[:3]:
            slot = item_slot(x.get("type"))
            if slot in out:
                out[slot] = str(x.get("id") or "")
        return (out["top"], out["bottom"], out["shoes"])

    def slot_distance(a: tuple[str, str, str], b: tuple[str, str, str]) -> int:
        # Distance in [0..3] across (top, bottom, shoes) slot identities.
        return sum(1 for i in range(3) if a[i] != b[i])

    for r in picked:
        seen_triplets.add(key_for(r))
        for x in r[:3]:
            sid = str(x.get("id") or "")
            if not sid or _is_hypothetical_item_id(sid):
                continue
            slot = item_slot(x.get("type"))
            if slot in {"top", "bottom"}:
                used_top_bottom.add(sid)
            elif slot == "shoes":
                used_shoes.add(sid)

    while len(picked) < target:
        strict_min_distance = 2
        if len(picked) >= 3:
            strict_min_distance = 1
        best_row: list[dict[str, Any]] | None = None
        best_score = -10**9
        best_sig: tuple[str, str, str] | None = None
        picked_sigs = [slot_signature(r) for r in picked]
        for row in triplets:
            if not _triplet_disjoint_ids_valid(row):
                continue
            row_key = key_for(row)
            if row_key in seen_triplets:
                # Hard block exact duplicates unless absolutely no other candidate exists.
                continue
            row_sig = slot_signature(row)
            if picked_sigs and min(slot_distance(row_sig, ps) for ps in picked_sigs) < strict_min_distance:
                # Too visually similar to an existing look.
                continue
            score = 0
            # Strongly prefer new tops/bottoms to keep looks distinct.
            for x in row[:3]:
                sid = str(x.get("id") or "")
                if not sid or _is_hypothetical_item_id(sid):
                    continue
                slot = item_slot(x.get("type"))
                if slot in {"top", "bottom"}:
                    # Keep tops/bottoms varied much more strongly than shoes.
                    score += 8 if sid not in used_top_bottom else -8
                elif slot == "shoes":
                    score += 1 if sid not in used_shoes else -1
            if score > best_score:
                best_score = score
                best_row = row
                best_sig = row_sig

        if best_row is None:
            # Relax similarity threshold once; still avoid exact duplicate triplets.
            if strict_min_distance > 0:
                strict_min_distance = 0
                for row in triplets:
                    if not _triplet_disjoint_ids_valid(row):
                        continue
                    row_key = key_for(row)
                    if row_key in seen_triplets:
                        continue
                    row_sig = slot_signature(row)
                    score = 0
                    for x in row[:3]:
                        sid = str(x.get("id") or "")
                        if not sid or _is_hypothetical_item_id(sid):
                            continue
                        slot = item_slot(x.get("type"))
                        if slot in {"top", "bottom"}:
                            score += 8 if sid not in used_top_bottom else -8
                        elif slot == "shoes":
                            score += 1 if sid not in used_shoes else -1
                    if picked_sigs and min(slot_distance(row_sig, ps) for ps in picked_sigs) < strict_min_distance:
                        score -= 4
                    if score > best_score:
                        best_score = score
                        best_row = row
                        best_sig = row_sig
            if best_row is None:
                break

        picked.append(list(best_row))
        seen_triplets.add(key_for(best_row))
        if best_sig is None:
            best_sig = slot_signature(best_row)
        for x in best_row[:3]:
            sid = str(x.get("id") or "")
            if not sid or _is_hypothetical_item_id(sid):
                continue
            slot = item_slot(x.get("type"))
            if slot in {"top", "bottom"}:
                used_top_bottom.add(sid)
            elif slot == "shoes":
                used_shoes.add(sid)

    return picked, len(picked) > len(rows)


def _should_skip_optional_outer_layers(flags: dict[str, bool], wb: str) -> bool:
    if flags.get("athletic"):
        return True
    if flags.get("casual_outdoor") and wb in {"mild", "warm", "hot"}:
        return True
    if wb in {"hot", "warm"} and not flags.get("business") and not flags.get("formal_plus"):
        return True
    return False


def _apply_optional_layers(
    rows: list[list[dict[str, Any]]],
    layers: list[dict[str, Any]],
    *,
    formality_src: dict[str, Any],
    pattern_src: dict[str, Any],
    global_used: set[str],
    skip_layers: bool = False,
) -> None:
    if skip_layers:
        return
    for row in rows:
        occupied = {str(x["id"]) for x in row if x.get("id") and not _is_hypothetical_item_id(x.get("id"))}
        for ly in layers:
            lid = str(ly.get("id") or "")
            if not lid or lid in global_used or lid in occupied:
                continue
            if formality_compatible(formality_src.get("formality"), ly.get("formality")) and pattern_compatible(
                pattern_src.get("pattern"), ly.get("pattern")
            ):
                row.append(ly)
                global_used.add(lid)
                break


def _partition_wardrobe_slots(wardrobe_items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    pools: dict[str, list[dict[str, Any]]] = {"top": [], "bottom": [], "shoes": [], "layer": []}
    for w in wardrobe_items:
        if w.get("id") is None:
            continue
        sl = item_slot(w.get("type"))
        if sl in pools:
            pools[sl].append(w)
    return pools


def _shopping_payload_empty_wardrobe(
    candidate: dict[str, Any],
    pools: dict[str, list[dict[str, Any]]],
    *,
    include_hypothetical: bool,
) -> dict[str, Any]:
    c_slot = item_slot(candidate.get("type")) if (include_hypothetical and candidate.get("type")) else None
    buys: list[str] = []
    if len(pools["top"]) == 0 and c_slot != "top":
        buys.append("A versatile top (t-shirt, blouse, or button-down) in a neutral you like.")
    if len(pools["bottom"]) == 0 and c_slot != "bottom":
        buys.append("One solid bottom (jeans, trousers, or a skirt) that mixes with your tops.")
    if len(pools["shoes"]) == 0 and c_slot != "shoes":
        buys.append("One pair of everyday shoes (sneakers, loafers, or boots) for your usual occasions.")
    if not buys:
        buys.append(
            "More distinct tops and bottoms digitized in Wardrobe so we can build four separate looks "
            "(shoes can repeat across looks)."
        )
    msg = (
        "We could not build a full top + bottom + shoes outfit from your digitized wardrobe yet. "
        "Add or digitize the basics below, then generate again."
    )
    return {"message": msg, "suggested_buys": buys}


def _primary_display_item(outfit_items: list[dict[str, Any]]) -> dict[str, Any]:
    for prefer_slot in ("bottom", "top", "shoes", "layer"):
        for it in outfit_items:
            if item_slot(it.get("type")) != prefer_slot:
                continue
            if _is_hypothetical_item_id(it.get("id")):
                continue
            if it.get("image_url"):
                return it
    for it in outfit_items:
        if not _is_hypothetical_item_id(it.get("id")):
            return it
    return outfit_items[0]


@traceable(name="outfits.structured.build_rows", run_type="chain", tags=["outfits", "structured"])
def _build_structured_outfit_rows(
    *,
    wardrobe_items: list[dict[str, Any]],
    candidate: dict[str, Any],
    color_season: str | None,
    include_hypothetical: bool,
    skip_optional_layers: bool = False,
) -> tuple[list[list[dict[str, Any]]], dict[str, int], bool]:
    """
    Returns (rows, pool_counts, used_dfs_fallback).
    """
    pools = _partition_wardrobe_slots(wardrobe_items)
    counts = {k: len(v) for k, v in pools.items()}

    rank_c = (
        candidate
        if (include_hypothetical and candidate and candidate.get("type"))
        else _neutral_rank_candidate()
    )
    for key in ("top", "bottom", "shoes", "layer"):
        pools[key] = sorted(
            pools[key],
            key=lambda w: _rank_anchor(rank_c, w, color_season),
            reverse=True,
        )

    tops, bottoms, shoes, layers = (
        pools["top"],
        pools["bottom"],
        pools["shoes"],
        pools["layer"],
    )

    use_hyp = bool(
        include_hypothetical
        and candidate
        and candidate.get("type")
        and item_slot(candidate.get("type")) in {"top", "bottom", "shoes"}
    )
    hyp = _hypothetical_item_row(candidate) if use_hyp else None
    c_slot = item_slot(candidate.get("type")) if use_hyp else ""

    used: set[str] = set()
    greedy_rows: list[list[dict[str, Any]]] = []

    def next_unused(pool: list[dict[str, Any]]) -> dict[str, Any] | None:
        for w in pool:
            sid = str(w.get("id") or "")
            if sid and sid not in used:
                return w
        return None

    def mark_used_disjoint_slots(row: list[dict[str, Any]]) -> None:
        for w in row[:3]:
            sid = str(w.get("id") or "")
            if not sid or _is_hypothetical_item_id(sid):
                continue
            if item_slot(w.get("type")) in {"top", "bottom"}:
                used.add(sid)

    for _ in range(4):
        top = hyp if c_slot == "top" else next_unused(tops)
        bottom = hyp if c_slot == "bottom" else next_unused(bottoms)
        shoe = hyp if c_slot == "shoes" else next_unused(shoes)
        if top is None or bottom is None or shoe is None:
            break
        row = [top, bottom, shoe]
        if not _triplet_disjoint_ids_valid(row):
            break
        mark_used_disjoint_slots(row)
        greedy_rows.append(row)

    triplets = _iter_triplets(tops, bottoms, shoes, hyp=hyp, c_slot=c_slot, cap=10)
    dfs_rows = _dfs_best_disjoint_rows(triplets, max_outfits=4, cap_triplets=72)
    used_dfs = len(dfs_rows) > len(greedy_rows)
    rows = dfs_rows if used_dfs else greedy_rows
    rows, used_reuse_fill = _ensure_four_rows_with_reuse(rows, triplets, target=4)

    layer_src = candidate if use_hyp else rank_c
    layer_used: set[str] = set()
    for r in rows:
        for piece in r:
            pid = str(piece.get("id") or "")
            if pid and not _is_hypothetical_item_id(pid):
                layer_used.add(pid)
    _apply_optional_layers(
        rows,
        layers,
        formality_src=layer_src,
        pattern_src=layer_src,
        global_used=layer_used,
        skip_layers=skip_optional_layers,
    )

    return rows, counts, used_dfs or used_reuse_fill


@traceable(name="outfits.generate", run_type="chain", tags=["outfits"])
async def generate_outfits(payload: dict[str, Any]) -> dict[str, Any]:
    occasion = str(payload.get("occasion") or "").strip()
    vibe = str(payload.get("vibe") or "").strip()
    weather_temp = _parse_weather_temp(payload.get("weather_temp"))
    weather_conditions = str(payload.get("weather_conditions") or "").strip() or None
    raw_c = payload.get("candidate")
    candidate: dict[str, Any] = raw_c if isinstance(raw_c, dict) else {}
    include_hypothetical = bool(payload.get("include_hypothetical"))
    requested_engine = str(payload.get("engine") or "").strip().lower()

    wardrobe_items = wardrobe_db.list_wardrobe_items()
    color_season = user_profile.get_color_season()
    trends = trends_db.get_trends_for_user(limit=10)
    occ_flags = _occasion_flags(occasion, vibe)
    wb = _weather_bucket(weather_temp, weather_conditions)

    candidate_type = _norm_type(candidate.get("type"))
    rows, pool_counts, used_dfs_fallback = _build_structured_outfit_rows(
        wardrobe_items=wardrobe_items,
        candidate=candidate,
        color_season=color_season,
        include_hypothetical=include_hypothetical,
        skip_optional_layers=_should_skip_optional_outer_layers(occ_flags, wb),
    )
    generation_path = "structured_slots"
    effective_engine = "structured"
    react_meta: dict[str, Any] = {}

    if requested_engine == "react":
        use_hyp_for_react = bool(
            include_hypothetical
            and candidate
            and candidate.get("type")
            and item_slot(candidate.get("type")) in {"top", "bottom", "shoes"}
        )
        react_hyp = _hypothetical_item_row(candidate) if use_hyp_for_react else None
        react_c_slot = item_slot(candidate.get("type")) if use_hyp_for_react else ""
        react = await run_llm_outfit_recommender(
            candidate=candidate,
            wardrobe_items=wardrobe_items,
            color_season=color_season,
            occasion=occasion,
            vibe=vibe,
            weather_temp=weather_temp,
            weather_conditions=weather_conditions,
        )
        react_meta = {
            "react_success": bool(react.get("success")),
            "react_reason": react.get("reason"),
            "react_outfits_returned": len(react.get("outfits") or []),
        }
        react_rows: list[list[dict[str, Any]]] = []
        react_selected_ids: list[list[str]] = []
        react_selected_reasons: list[str] = []
        react_seen_signatures: set[tuple[str, ...]] = set()
        by_id = {str(w.get("id")): w for w in wardrobe_items if w.get("id") is not None}
        for rec in react.get("outfits") or []:
            ids = [str(x) for x in rec.get("item_ids", [])]
            sig = tuple(ids[:4])
            if sig in react_seen_signatures:
                continue
            chosen = [by_id[i] for i in ids if i in by_id]
            if len(chosen) >= 2:
                row = _inject_hypothetical_into_row(chosen[:4], hyp=react_hyp, c_slot=react_c_slot)
                react_rows.append(row)
                react_selected_ids.append(ids[:4])
                react_selected_reasons.append(str(rec.get("reasoning") or "").strip())
                react_seen_signatures.add(sig)
            if len(react_rows) >= 4:
                break
        react_meta["react_selected_ids"] = react_selected_ids
        react_meta["react_selected_reasoning"] = react_selected_reasons
        # Accept React primary only if it is not overly repetitive on core slots.
        unique_tops = _unique_slot_ids(react_rows, "top")
        unique_bottoms = _unique_slot_ids(react_rows, "bottom")
        unique_shoes = _unique_slot_ids(react_rows, "shoes")
        min_tops = min(2, int(pool_counts.get("top", 0)))
        min_bottoms = min(2, int(pool_counts.get("bottom", 0)))
        min_shoes = min(2, int(pool_counts.get("shoes", 0)))
        if react_c_slot == "top":
            min_tops = 0
        elif react_c_slot == "bottom":
            min_bottoms = 0
        elif react_c_slot == "shoes":
            min_shoes = 0
        react_diversity_ok = (
            len(unique_tops) >= min_tops
            and len(unique_bottoms) >= min_bottoms
            and len(unique_shoes) >= min_shoes
        )
        react_meta["react_slot_diversity"] = {
            "tops": len(unique_tops),
            "bottoms": len(unique_bottoms),
            "shoes": len(unique_shoes),
            "required": {"tops": min_tops, "bottoms": min_bottoms, "shoes": min_shoes},
        }
        if len(react_rows) >= 4:
            if react_diversity_ok:
                rows = react_rows
                used_dfs_fallback = False
                generation_path = "react_primary"
                effective_engine = "react"
            else:
                generation_path = "structured_fallback"
                effective_engine = "structured"
                react_meta["react_fallback_reason"] = (
                    "React output was too repetitive across core slots; switched to structured fallback "
                    f"(slot diversity={react_meta.get('react_slot_diversity')})."
                )
        else:
            generation_path = "structured_fallback"
            effective_engine = "structured"
            react_meta["react_fallback_reason"] = (
                f"React produced {len(react_rows)} usable outfit(s), but 4 are required. "
                f"Reason={react_meta.get('react_reason') or 'insufficient_valid_outfits'}."
            )

    pipeline_stages: list[dict[str, Any]] = []
    if requested_engine == "react":
        pipeline_stages.append(
            {
                "name": "react_primary",
                "outcome": "success" if generation_path == "react_primary" else "failed",
                "detail": (
                    f"returned={react_meta.get('react_outfits_returned', 0)}, "
                    f"usable={len(react_meta.get('react_selected_ids') or [])}, "
                    f"reason={react_meta.get('react_reason')}"
                ),
            }
        )
        pipeline_stages.append(
            {
                "name": "structured_fallback",
                "outcome": "success" if rows and generation_path == "structured_fallback" else "skipped",
                "detail": (
                    f"{react_meta.get('react_fallback_reason') or 'not_used'}; "
                    f"pools={pool_counts}, built={len(rows)}, dfs_fallback={used_dfs_fallback}"
                ),
            }
        )
    else:
        pipeline_stages.append(
            {
                "name": "structured_outfits",
                "outcome": "success" if rows else "failed",
                "detail": f"pools={pool_counts}, built={len(rows)}, dfs_fallback={used_dfs_fallback}",
            }
        )

    if not rows:
        shop = _shopping_payload_empty_wardrobe(
            candidate,
            _partition_wardrobe_slots(wardrobe_items),
            include_hypothetical=include_hypothetical,
        )
        return {
            "outfits": [],
            "candidate": candidate,
            "color_season": color_season,
            "shopping_message": shop["message"],
            "suggested_buys": shop["suggested_buys"],
            "debug": {
                "engine": effective_engine,
                "generation_path": generation_path,
                "pipeline_stages": pipeline_stages,
                "candidate_type": candidate_type,
                "pool_counts": pool_counts,
                "outfits_built": 0,
                "include_hypothetical": include_hypothetical,
                "dfs_fallback_used": False,
                **react_meta,
            },
        }

    shortfall_msg: str | None = None
    if len(rows) < 4:
        shortfall_msg = (
            f"Showing {len(rows)} of 4 outfits. Each look uses different tops and bottoms; the same shoes can "
            "appear in multiple looks. Add more digitized tops and bottoms (or turn off “hypothetical purchase” "
            "if it occupies a slot) to reach four looks."
        )

    rank_c = (
        candidate
        if (include_hypothetical and candidate and candidate.get("type"))
        else _neutral_rank_candidate()
    )

    outfits: list[dict[str, Any]] = []
    for outfit_items in rows:
        anchor = _primary_display_item(outfit_items)
        wardrobe_only = [x for x in outfit_items if not _is_hypothetical_item_id(x.get("id"))]
        c_color = _color_match_score(color_season, _pick_color(rank_c.get("primary_color")))
        w_colors = [
            _color_match_score(color_season, _pick_color(x.get("primary_color"))) for x in wardrobe_only
        ]
        color_avg = sum(w_colors) / max(len(w_colors), 1)
        color_mix = c_color * 0.35 + color_avg * 0.65
        c_season = seasonal_versatility(rank_c)
        coherence_vals = [_style_coherence_ok(rank_c, it) for it in wardrobe_only]
        coherence = sum(coherence_vals) / max(len(coherence_vals), 1)
        wcheck = weather_check(outfit_items, weather_temp, weather_conditions)
        tcheck = trend_check(outfit_items, trends, color_season)
        weather_score = float(wcheck.get("weather_score") or 0.5)
        trend_score = float(tcheck.get("trend_score") or 0.5)
        fills = float(len(outfit_items))
        expected = 3.0
        completeness = min(1.0, fills / expected)

        pw = _PREJUDGE_W
        overall_prejudge = (
            color_mix * pw["color_avg"]
            + c_season * pw["season"]
            + coherence * pw["coherence"]
            + weather_score * pw["weather"]
            + trend_score * pw["trend"]
            + completeness * _COMPLETENESS_WEIGHT
        )
        judge = await judge_outfit(
            outfit_items=outfit_items,
            occasion=occasion,
            vibe=vibe,
            weather_temp=weather_temp,
            weather_conditions=weather_conditions,
            color_season=color_season,
            trend_context=str([t.get("name") for t in trends[:5]]),
        )
        _jo = judge.get("overall_score")
        judge_overall_norm = max(0.0, min(1.0, float(_jo if _jo is not None else 6.0) / 10.0))
        prejudge_share = 1.0 - _JUDGE_BLEND
        overall = round((overall_prejudge * prejudge_share + judge_overall_norm * _JUDGE_BLEND) * 100, 1)

        reasoning_text = _compose_reasoning_text(
            outfit_items=outfit_items,
            judge=judge,
            generation_path=generation_path,
            occasion=occasion,
            vibe=vibe,
            color_season=color_season,
            weather_score=weather_score,
            trend_score=trend_score,
        )

        outfits.append(
            {
                "items": [
                    it.get("id")
                    for it in outfit_items
                    if it.get("id") is not None and not _is_hypothetical_item_id(it.get("id"))
                ],
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
                "reasoning": reasoning_text,
                "scores": {
                    "color_match": round(color_mix, 2),
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

    return {
        "outfits": outfits,
        "candidate": candidate,
        "color_season": color_season,
        "shopping_message": shortfall_msg,
        "suggested_buys": None
        if len(rows) >= 4
        else [
            "Add more digitized tops and bottoms so a fourth look can use different upper/lower pieces "
            "(shoes may repeat across outfits)."
        ],
        "debug": {
            "engine": effective_engine,
            "generation_path": generation_path,
            "pipeline_stages": pipeline_stages,
            "candidate_type": candidate_type,
            "pool_counts": pool_counts,
            "outfits_built": len(rows),
            "include_hypothetical": include_hypothetical,
            "dfs_fallback_used": used_dfs_fallback,
            **react_meta,
        },
    }


