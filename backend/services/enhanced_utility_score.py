"""
Additive layer on top of calculate_utility_score():
- preference-based adjusted score (does not change base score)
- async Gemini explanation with JSON output + fallback
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from config import settings
from services.utility_score import (
    _norm_color,
    _norm_type,
    calculate_utility_score,
)

log = logging.getLogger(__name__)

_DEFAULT_GEMINI_MODELS = ("gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash")


def _gemini_model_chain() -> list[str]:
    raw = (settings.gemini_model or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts if parts else list(_DEFAULT_GEMINI_MODELS)


def _gemini_url(model_id: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"


NO_GEMINI_KEY_EXPLANATION: dict[str, Any] = {
    "summary": "Decent",
    "reasoning": [
        "GEMINI_API_KEY is missing or empty after loading backend/.env and backend/env. Use Google AI Studio to create a key, add GEMINI_API_KEY=... to one of those files, then restart uvicorn.",
        "Config loads env from the backend folder by absolute path (not the shell cwd).",
    ],
    "confidence": 0.25,
}

# Gemini JSON schema (subset supported by Generative Language API) — improves parse reliability when accepted.
_GEMINI_EXPLANATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "enum": ["Great buy", "Decent", "Skip"]},
        "reasoning": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["summary", "reasoning", "confidence"],
}

_FREQUENT_THRESHOLD = 2


def _apply_price_value_adjustment(
    adjusted_score: float,
    *,
    price: float | None,
    cost_per_wear: float | None,
) -> dict[str, Any]:
    """
    Penalize expensive items when utility coverage is weak.
    Higher adjusted score tolerates somewhat higher CPW before penalty kicks in.
    """
    if price is None or price <= 0 or cost_per_wear is None:
        return {
            "score_after_price": round(float(adjusted_score), 1),
            "price_value_penalty": 0.0,
            "max_reasonable_cpw": None,
            "expensive_for_value": False,
        }

    # Dynamic CPW ceiling: high-utility items can justify more spend.
    # score=100 => ~18; score=50 => ~12; score=0 => ~6
    max_reasonable_cpw = 6.0 + (float(adjusted_score) / 100.0) * 12.0
    ratio = float(cost_per_wear) / max_reasonable_cpw if max_reasonable_cpw > 0 else 1.0
    if ratio <= 1.0:
        return {
            "score_after_price": round(float(adjusted_score), 1),
            "price_value_penalty": 0.0,
            "max_reasonable_cpw": round(max_reasonable_cpw, 2),
            "expensive_for_value": False,
        }

    # Penalty ramps quickly once CPW exceeds the dynamic ceiling.
    penalty = min(35.0, (ratio - 1.0) * 28.0)
    score_after = max(0.0, min(100.0, float(adjusted_score) - penalty))
    return {
        "score_after_price": round(score_after, 1),
        "price_value_penalty": round(penalty, 1),
        "max_reasonable_cpw": round(max_reasonable_cpw, 2),
        "expensive_for_value": True,
    }


def _heuristic_ai_explanation(
    breakdown: dict[str, Any],
    adjusted_score: float | None,
) -> dict[str, Any]:
    """
    When Gemini returns 200 but JSON parse fails (or all models fail), align headline with
    the numeric utility score so a 72 does not show the hardcoded 'Decent' failure copy.
    """
    s = float(adjusted_score if adjusted_score is not None else breakdown.get("score") or 0)
    s = max(0.0, min(100.0, s))
    if s >= 65:
        label = "Great buy"
        conf = 0.62
    elif s >= 38:
        label = "Decent"
        conf = 0.55
    else:
        label = "Skip"
        conf = 0.48

    op = breakdown.get("outfit_potential")
    cpw = breakdown.get("cost_per_wear")
    price_penalty = float(breakdown.get("price_value_penalty") or 0.0)
    expensive_for_value = bool(breakdown.get("expensive_for_value"))
    cm = breakdown.get("color_match")

    parts2: list[str] = []
    if op is not None:
        parts2.append(f"{op} in-app outfit pairing(s)")
    if cm is not None:
        try:
            parts2.append(f"color match ~{int(float(cm) * 100)}% vs your season")
        except (TypeError, ValueError):
            pass
    line2 = " · ".join(parts2) if parts2 else "Add more catalogued pieces to strengthen pairing and color signals."

    cpw_line = f"Cost per wear ~${cpw} at your price." if cpw is not None else "Add a price to see cost per wear."
    if expensive_for_value and cpw is not None:
        cap = breakdown.get("max_reasonable_cpw")
        cpw_line = (
            f"Cost per wear ~${cpw} is high for current closet utility"
            + (f" (target <= ~${cap})." if cap is not None else ".")
        )

    return {
        "summary": label,
        "reasoning": [
            f"Utility model ~{s:.0f}/100 (wardrobe + palette rules).",
            line2,
            f"Price-value adjustment: -{price_penalty:.1f} points due to high price versus predicted re-use." if price_penalty > 0 else "Price is within expected range for the predicted re-use level.",
            f"{cpw_line} Google AI did not return a usable JSON summary this time — if this repeats, check server WARNING logs and GEMINI_MODEL.",
        ],
        "confidence": conf,
    }


def adjust_score_with_preferences(score: float, item: dict, user_preferences: dict) -> float:
    """
    Light touch on top of the base utility score.
    preferred_colors / preferred_types: map of key -> interaction count (int).
    interaction_history: list of events, e.g. {"action": "dislike", "type": "...", "primary_color": "..."}
    """
    preferred_colors = user_preferences.get("preferred_colors") or {}
    preferred_types = user_preferences.get("preferred_types") or {}
    interaction_history = user_preferences.get("interaction_history") or []

    adjusted = float(score)
    color_key = _norm_color(item.get("primary_color"))
    type_key = _norm_type(item.get("type"))

    if color_key and isinstance(preferred_colors, dict):
        c = preferred_colors.get(color_key)
        if isinstance(c, (int, float)) and c >= _FREQUENT_THRESHOLD:
            adjusted += 5

    if type_key and isinstance(preferred_types, dict):
        t = preferred_types.get(type_key)
        if isinstance(t, (int, float)) and t >= _FREQUENT_THRESHOLD:
            adjusted += 5

    disliked_similar = False
    if isinstance(interaction_history, list):
        for ev in interaction_history:
            if not isinstance(ev, dict):
                continue
            if str(ev.get("action", "")).lower() != "dislike":
                continue
            ev_c = _norm_color(ev.get("primary_color"))
            ev_t = _norm_type(ev.get("type"))
            if type_key and ev_t and ev_t == type_key:
                disliked_similar = True
                break
            if color_key and ev_c and ev_c == color_key:
                disliked_similar = True
                break

    if disliked_similar:
        adjusted -= 5

    return max(0.0, min(100.0, round(adjusted, 1)))


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    for prefix in ("```json", "```"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return text


def _extract_json_object(raw: str) -> str | None:
    """First balanced {...} via JSONDecoder (greedy regex breaks on nested objects)."""
    s = _strip_json_fences(raw)
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch != "{":
            continue
        try:
            _, end = dec.raw_decode(s[i:])
            return s[i : i + end]
        except json.JSONDecodeError:
            continue
    return None


def _parse_ai_json(raw: str) -> dict[str, Any] | None:
    blob = _extract_json_object(raw)
    if not blob:
        return None
    try:
        out = json.loads(blob)
    except json.JSONDecodeError:
        return None
    if not isinstance(out, dict):
        return None
    summary = out.get("summary")
    if summary is not None and not isinstance(summary, str):
        summary = str(summary).strip()
    if not isinstance(summary, str) or not summary.strip():
        return None
    summary = summary.strip()
    if summary not in ("Great buy", "Decent", "Skip"):
        # Allow minor variants from the model
        sl = summary.lower()
        if "great" in sl or "good buy" in sl:
            summary = "Great buy"
        elif "skip" in sl or "pass" in sl:
            summary = "Skip"
        else:
            summary = "Decent"

    reasoning = out.get("reasoning")
    bullets: list[str] = []
    if isinstance(reasoning, list):
        bullets = [str(x).strip() for x in reasoning if str(x).strip()][:3]
    elif isinstance(reasoning, str) and reasoning.strip():
        bullets = [reasoning.strip()]
    if len(bullets) < 1:
        return None

    confidence = out.get("confidence")
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    return {"summary": summary, "reasoning": bullets, "confidence": conf}


def _gemini_part_texts(data: dict[str, Any]) -> list[str]:
    """
    Collect user-visible text parts. Skips thought/reasoning parts (Gemini 2.x) so JSON
    is not merged with hidden chains (which breaks parsing).
    """
    err = data.get("error")
    if isinstance(err, dict):
        log.warning("Gemini API error field: %s", err.get("message", err))
        return []

    fb = data.get("promptFeedback")
    if isinstance(fb, dict) and fb.get("blockReason"):
        log.warning("Gemini promptFeedback blockReason=%s", fb.get("blockReason"))

    candidates = data.get("candidates")
    if not candidates or not isinstance(candidates, list):
        log.warning("Gemini no candidates; top-level keys=%s", list(data.keys()))
        return []
    c0 = candidates[0]
    if not isinstance(c0, dict):
        return []
    fr = c0.get("finishReason")
    if fr is not None and str(fr).upper() in ("SAFETY", "RECITATION", "OTHER", "BLOCKLIST"):
        log.warning("Gemini finishReason=%s", fr)
    if fr is not None and str(fr).upper() == "MAX_TOKENS":
        log.warning("Gemini finishReason=MAX_TOKENS (output may be truncated JSON)")

    content = c0.get("content")
    if not isinstance(content, dict):
        log.warning("Gemini candidate missing content; candidate keys=%s", list(c0.keys()))
        return []
    parts = content.get("parts")
    if not parts or not isinstance(parts, list):
        log.warning("Gemini missing content.parts")
        return []

    chunks: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        if p.get("thought") is True:
            continue
        t = p.get("text")
        if isinstance(t, str) and t.strip():
            chunks.append(t.strip())
    return chunks


def _parse_ai_json_from_texts(texts: list[str]) -> dict[str, Any] | None:
    """Try last chunk first (final model answer), then earlier chunks, then newline-joined."""
    for chunk in reversed(texts):
        parsed = _parse_ai_json(chunk)
        if parsed:
            return parsed
    if len(texts) > 1:
        return _parse_ai_json("\n".join(texts))
    return None


async def generate_ai_explanation(
    item: dict,
    score_breakdown: dict,
    user_profile: dict,
    *,
    adjusted_score: float | None = None,
) -> dict[str, Any]:
    """
    Gemini JSON-only explanation. On failure, score-based heuristic (not generic DEFAULT copy).
    """
    if not settings.gemini_api_key or not str(settings.gemini_api_key).strip():
        return dict(NO_GEMINI_KEY_EXPLANATION)

    palette = user_profile.get("color_season") or user_profile.get("color_palette") or "unknown"
    prompt = f"""You are a concise shopping assistant. Output ONLY a single JSON object. No markdown, no code fences, no extra keys or text.

Item:
{json.dumps(item, default=str)}

Utility score breakdown (numeric MVP):
{json.dumps(score_breakdown, default=str)}

User color palette / season (string): {palette}

Return exactly this JSON shape:
{{"summary": "Great buy" | "Decent" | "Skip", "reasoning": ["bullet1", "bullet2", "bullet3"], "confidence": 0.0-1.0}}

Rules:
- reasoning has at most 3 short strings
- mention tradeoffs (fit with wardrobe signals, seasons, color match vs placeholders)
- confidence reflects how certain you are given limited data"""

    base_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }

    gen_plain = {"temperature": 0.2, "maxOutputTokens": 1024}
    gen_json = {**gen_plain, "responseMimeType": "application/json"}
    gen_json_schema = {
        **gen_json,
        "responseSchema": _GEMINI_EXPLANATION_SCHEMA,
    }

    for model_id in _gemini_model_chain():
        api_url = _gemini_url(model_id)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    api_url,
                    params={"key": settings.gemini_api_key},
                    json={**base_payload, "generationConfig": gen_json_schema},
                )
                if r.status_code == 400:
                    log.warning(
                        "Gemini model=%s JSON+schema rejected (%s), retrying JSON without schema",
                        model_id,
                        r.text[:200],
                    )
                    r = await client.post(
                        api_url,
                        params={"key": settings.gemini_api_key},
                        json={**base_payload, "generationConfig": gen_json},
                    )
                if r.status_code == 400:
                    log.warning(
                        "Gemini model=%s JSON mode rejected (%s), retrying plain text",
                        model_id,
                        r.text[:200],
                    )
                    r = await client.post(
                        api_url,
                        params={"key": settings.gemini_api_key},
                        json={**base_payload, "generationConfig": gen_plain},
                    )
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as e:
            log.warning(
                "Gemini model=%s HTTP %s: %s",
                model_id,
                e.response.status_code,
                e.response.text[:500] if e.response.text else "",
            )
            continue
        except Exception:
            log.warning("Gemini model=%s request failed", model_id, exc_info=True)
            continue

        if not isinstance(data, dict):
            continue

        texts = _gemini_part_texts(data)
        if not texts:
            log.warning("Gemini model=%s returned no usable text parts", model_id)
            continue

        parsed = _parse_ai_json_from_texts(texts)
        if parsed:
            return parsed
        log.warning(
            "Gemini model=%s could not parse JSON (last chunk, first 240 chars): %s",
            model_id,
            texts[-1][:240],
        )

    return _heuristic_ai_explanation(score_breakdown, adjusted_score)


async def enhanced_utility_score(
    item: dict,
    user_profile: dict,
    wardrobe: list,
    user_preferences: dict,
    user_trends: list,
    wardrobe_analytics: dict,
) -> dict:
    """
    Wraps calculate_utility_score (unchanged base score), adds preference adjustment + AI explanation.
    """
    _ = wardrobe
    _ = user_trends
    _ = wardrobe_analytics
    base_result = calculate_utility_score(item)
    preference_adjusted = adjust_score_with_preferences(base_result["score"], item, user_preferences)
    price_adj = _apply_price_value_adjustment(
        preference_adjusted,
        price=float(item.get("price")) if item.get("price") not in (None, "") else None,
        cost_per_wear=float(base_result["cost_per_wear"]) if base_result.get("cost_per_wear") is not None else None,
    )
    adjusted_score = float(price_adj["score_after_price"])
    enriched_breakdown = {**base_result, **price_adj}
    ai_explanation = await generate_ai_explanation(
        item, enriched_breakdown, user_profile, adjusted_score=adjusted_score
    )

    return {
        "score": base_result["score"],
        "adjusted_score": adjusted_score,
        "preference_adjusted_score": preference_adjusted,
        "breakdown": enriched_breakdown,
        "cost_per_wear": base_result["cost_per_wear"],
        "ai_explanation": ai_explanation,
        "scored_item": item,
    }
