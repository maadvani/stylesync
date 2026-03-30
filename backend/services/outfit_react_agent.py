"""
Gemini-powered ReAct loop for outfit generation tool orchestration.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import settings
from services import trends_db
from services.outfit_tools import check_style_rules, search_wardrobe, trend_check, weather_check

log = logging.getLogger(__name__)

_VALID_TOOLS = {"SEARCH_WARDROBE", "CHECK_STYLE_RULES", "WEATHER_CHECK", "TREND_CHECK", "FINAL"}


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    s = raw.strip()
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(s[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _gemini_text(data: dict[str, Any]) -> str | None:
    cands = data.get("candidates")
    if not isinstance(cands, list) or not cands:
        return None
    c0 = cands[0]
    if not isinstance(c0, dict):
        return None
    content = c0.get("content")
    if not isinstance(content, dict):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list):
        return None
    chunks: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        if p.get("thought") is True:
            continue
        t = p.get("text")
        if isinstance(t, str) and t.strip():
            chunks.append(t.strip())
    if not chunks:
        return None
    return chunks[-1]


def _gemini_url() -> str:
    model = (settings.outfits_react_model or "").strip() or "gemini-2.0-flash"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def _react_step(prompt: str) -> dict[str, Any] | None:
    key = (settings.gemini_api_key or "").strip()
    if not key:
        return None
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            r = await client.post(_gemini_url(), params={"key": key}, json=payload)
            if r.status_code == 400:
                fallback_payload = {
                    "contents": payload["contents"],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512},
                }
                r = await client.post(_gemini_url(), params={"key": key}, json=fallback_payload)
            r.raise_for_status()
            data = r.json()
        if not isinstance(data, dict):
            return None
        text = _gemini_text(data)
        if not text:
            return None
        obj = _extract_json_object(text)
        if not isinstance(obj, dict):
            return None
        tool = str(obj.get("tool") or "").upper()
        if tool not in _VALID_TOOLS:
            return None
        obj["tool"] = tool
        if not isinstance(obj.get("tool_input"), dict):
            obj["tool_input"] = {}
        return obj
    except Exception:
        log.warning("Outfits ReAct step failed", exc_info=True)
        return None


def _brief_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for w in items[:40]:
        out.append(
            {
                "id": w.get("id"),
                "type": w.get("type"),
                "primary_color": w.get("primary_color"),
                "pattern": w.get("pattern"),
                "formality": w.get("formality"),
                "seasons": w.get("seasons") or [],
            }
        )
    return out


def _make_prompt(
    *,
    candidate: dict[str, Any],
    occasion: str,
    vibe: str,
    weather_temp: int | None,
    weather_conditions: str | None,
    state: dict[str, Any],
    trace: list[dict[str, Any]],
) -> str:
    return f"""You are a ReAct outfit planner.
Choose exactly ONE tool per step.
Return ONLY JSON:
{{
  "thought": "brief",
  "tool": "SEARCH_WARDROBE|CHECK_STYLE_RULES|WEATHER_CHECK|TREND_CHECK|FINAL",
  "tool_input": {{}},
  "final": {{"selected_item_ids": ["id1","id2","id3","id4"]}}
}}

Context:
- candidate: {json.dumps(candidate, default=str)}
- occasion: {occasion}
- vibe: {vibe}
- weather_temp: {weather_temp}
- weather_conditions: {weather_conditions}
- state: {json.dumps(state, default=str)}
- trace_len: {len(trace)}

Tool docs:
1) SEARCH_WARDROBE tool_input:
{{"types":["top","pants"],"max_formality_gap":2,"candidate_formality":3,"seasons":["fall"],"colors":["navy"]}}
2) CHECK_STYLE_RULES tool_input:
{{"item_ids":["..."]}}
3) WEATHER_CHECK tool_input:
{{"item_ids":["..."]}}
4) TREND_CHECK tool_input:
{{"item_ids":["..."]}}
5) FINAL tool_input: {{}}

Use FINAL only when state has a clear item_ids candidate list.
Prefer <= 4 ids for selected_item_ids.
"""


async def run_react_outfit_planner(
    *,
    candidate: dict[str, Any],
    wardrobe_items: list[dict[str, Any]],
    color_season: str | None,
    occasion: str,
    vibe: str,
    weather_temp: int | None,
    weather_conditions: str | None,
) -> dict[str, Any]:
    max_steps = max(1, int(settings.outfits_react_max_steps or 6))
    trace: list[dict[str, Any]] = []
    state: dict[str, Any] = {
        "candidate_pool_ids": [],
        "valid_ids": [],
        "weather_score": None,
        "trend_score": None,
    }
    item_by_id = {str(w.get("id")): w for w in wardrobe_items if w.get("id") is not None}
    trends = trends_db.get_trends_for_user(limit=10)
    success = False
    for step in range(max_steps):
        prompt = _make_prompt(
            candidate=candidate,
            occasion=occasion,
            vibe=vibe,
            weather_temp=weather_temp,
            weather_conditions=weather_conditions,
            state=state,
            trace=trace,
        )
        action = await _react_step(prompt)
        if not action:
            trace.append({"step": step + 1, "error": "no_action_from_model"})
            break
        tool = action["tool"]
        tin = action.get("tool_input") or {}
        record: dict[str, Any] = {"step": step + 1, "tool": tool, "tool_input": tin}

        if tool == "SEARCH_WARDROBE":
            found = search_wardrobe(
                wardrobe_items,
                types=tin.get("types"),
                max_formality_gap=tin.get("max_formality_gap"),
                candidate_formality=tin.get("candidate_formality") or candidate.get("formality"),
                seasons=tin.get("seasons"),
                colors=tin.get("colors"),
            )
            ids = [str(w.get("id")) for w in found if w.get("id") is not None]
            state["candidate_pool_ids"] = ids
            record["result_count"] = len(ids)
        elif tool == "CHECK_STYLE_RULES":
            ids = [str(x) for x in tin.get("item_ids", [])]
            items = [item_by_id[i] for i in ids if i in item_by_id]
            styled = check_style_rules(candidate, items)
            valid_ids = [str(w.get("id")) for w in styled["valid_items"] if w.get("id") is not None]
            state["valid_ids"] = valid_ids
            record["result_count"] = len(valid_ids)
        elif tool == "WEATHER_CHECK":
            ids = [str(x) for x in tin.get("item_ids", [])]
            items = [item_by_id[i] for i in ids if i in item_by_id]
            wc = weather_check(items, weather_temp, weather_conditions)
            state["weather_score"] = wc.get("weather_score")
            record["weather_score"] = wc.get("weather_score")
        elif tool == "TREND_CHECK":
            ids = [str(x) for x in tin.get("item_ids", [])]
            items = [item_by_id[i] for i in ids if i in item_by_id]
            tc = trend_check(items, trends, color_season)
            state["trend_score"] = tc.get("trend_score")
            record["trend_score"] = tc.get("trend_score")
        elif tool == "FINAL":
            final = action.get("final") or {}
            ids = [str(x) for x in final.get("selected_item_ids", []) if str(x) in item_by_id]
            record["selected_item_ids"] = ids
            if ids:
                success = True
                trace.append(record)
                return {
                    "success": True,
                    "selected_item_ids": ids,
                    "trace": trace,
                    "state": state,
                    "candidate_pool_preview": _brief_items([item_by_id[i] for i in ids[:8] if i in item_by_id]),
                }
        trace.append(record)

    # Fallback selection from current state
    pool_ids = state.get("valid_ids") or state.get("candidate_pool_ids") or list(item_by_id.keys())
    ids = [str(x) for x in pool_ids[:8] if str(x) in item_by_id]
    return {
        "success": success and bool(ids),
        "selected_item_ids": ids,
        "trace": trace,
        "state": state,
        "candidate_pool_preview": _brief_items([item_by_id[i] for i in ids[:8] if i in item_by_id]),
    }

