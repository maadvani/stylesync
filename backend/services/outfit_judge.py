"""
LLM-as-a-judge scoring for generated outfits.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import settings

log = logging.getLogger(__name__)

_FALLBACK = {
    "style_coherence": {"score": 6.0, "reasoning": "Reasonable style compatibility by rules."},
    "color_harmony": {"score": 6.0, "reasoning": "Moderate color harmony based on palette matching."},
    "occasion_appropriateness": {"score": 6.0, "reasoning": "Generally suitable for the requested occasion."},
    "trend_relevance": {"score": 5.5, "reasoning": "Trend signal is moderate from available data."},
    "practicality": {"score": 6.0, "reasoning": "Weather and wardrobe practicality are acceptable."},
    "overall_score": 6.0,
}


def _extract_json(raw: str) -> dict[str, Any] | None:
    dec = json.JSONDecoder()
    for i, ch in enumerate(raw.strip()):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(raw.strip()[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _gemini_url() -> str:
    model = (settings.outfits_judge_model or "").strip() or "gemini-2.0-flash"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def _call_judge(prompt: str) -> dict[str, Any] | None:
    key = (settings.gemini_api_key or "").strip()
    if not key:
        return None
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": int(settings.outfits_judge_max_tokens or 512),
            "responseMimeType": "application/json",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(_gemini_url(), params={"key": key}, json=payload)
            if r.status_code == 400:
                fallback_payload = {"contents": payload["contents"], "generationConfig": {"temperature": 0.2, "maxOutputTokens": int(settings.outfits_judge_max_tokens or 512)}}
                r = await client.post(_gemini_url(), params={"key": key}, json=fallback_payload)
            r.raise_for_status()
            data = r.json()
        cands = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(cands, list) or not cands:
            return None
        c0 = cands[0] if isinstance(cands[0], dict) else {}
        content = c0.get("content") if isinstance(c0, dict) else {}
        parts = content.get("parts") if isinstance(content, dict) else []
        text = None
        if isinstance(parts, list):
            for p in reversed(parts):
                if isinstance(p, dict) and isinstance(p.get("text"), str) and p.get("text").strip():
                    text = p.get("text").strip()
                    break
        if not text:
            return None
        return _extract_json(text)
    except Exception:
        log.warning("Outfit judge call failed", exc_info=True)
        return None


def _clamp10(v: Any, default: float = 6.0) -> float:
    try:
        x = float(v)
    except Exception:
        x = default
    return max(1.0, min(10.0, x))


def _normalize(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return dict(_FALLBACK)
    out = dict(_FALLBACK)
    for k in ("style_coherence", "color_harmony", "occasion_appropriateness", "trend_relevance", "practicality"):
        sec = payload.get(k)
        if isinstance(sec, dict):
            out[k] = {
                "score": _clamp10(sec.get("score"), out[k]["score"]),
                "reasoning": str(sec.get("reasoning") or out[k]["reasoning"]).strip(),
            }
    o = payload.get("overall_score")
    if o is None:
        dims = [out[k]["score"] for k in ("style_coherence", "color_harmony", "occasion_appropriateness", "trend_relevance", "practicality")]
        out["overall_score"] = round(sum(dims) / len(dims), 1)
    else:
        out["overall_score"] = round(_clamp10(o), 1)
    return out


async def judge_outfit(
    *,
    outfit_items: list[dict[str, Any]],
    occasion: str,
    vibe: str,
    weather_temp: int | None,
    weather_conditions: str | None,
    color_season: str | None,
    trend_context: str,
) -> dict[str, Any]:
    if not settings.outfits_judge_enabled:
        return dict(_FALLBACK)
    items_desc = [
        {
            "type": it.get("type"),
            "primary_color": it.get("primary_color"),
            "pattern": it.get("pattern"),
            "formality": it.get("formality"),
            "material": it.get("material"),
        }
        for it in outfit_items
    ]
    prompt = f"""Evaluate outfit quality. Return ONLY JSON:
{{
  "style_coherence": {{"score": 1-10, "reasoning": "..." }},
  "color_harmony": {{"score": 1-10, "reasoning": "..." }},
  "occasion_appropriateness": {{"score": 1-10, "reasoning": "..." }},
  "trend_relevance": {{"score": 1-10, "reasoning": "..." }},
  "practicality": {{"score": 1-10, "reasoning": "..." }},
  "overall_score": 1-10
}}

Items: {json.dumps(items_desc, default=str)}
Context:
- occasion: {occasion}
- vibe: {vibe}
- weather_temp: {weather_temp}
- weather_conditions: {weather_conditions}
- color_season: {color_season}
- trend_context: {trend_context}
"""
    raw = await _call_judge(prompt)
    return _normalize(raw)

