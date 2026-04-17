"""
Gemini-powered ReAct loop for outfit generation tool orchestration.
"""
from __future__ import annotations

import json
import logging
import asyncio
import re
import ast
from typing import Any

import httpx

from config import settings
from services import trends_db
from services.outfit_tools import check_style_rules, search_wardrobe, trend_check, weather_check

log = logging.getLogger(__name__)

_VALID_TOOLS = {"SEARCH_WARDROBE", "CHECK_STYLE_RULES", "WEATHER_CHECK", "TREND_CHECK", "FINAL"}

# Gemini structured output: forces valid JSON matching this shape (fallback if API rejects schema).
_OUTFIT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "outfits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_ids": {"type": "array", "items": {"type": "string"}},
                    "reasoning": {"type": "string"},
                },
                "required": ["item_ids", "reasoning"],
            },
        }
    },
    "required": ["outfits"],
}


def _normalize_item_ids(row: dict[str, Any]) -> list[str]:
    for k in ("item_ids", "itemIds", "wardrobe_item_ids", "wardrobe_ids", "ids", "items"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                loaded = _json_loads_with_balanced_fallback(s)
                if isinstance(loaded, list):
                    v = loaded
            elif "," in s:
                parts = [p.strip().strip('"\'') for p in s.split(",") if p.strip()]
                if len(parts) >= 2:
                    return parts
        if isinstance(v, list) and v:
            out: list[str] = []
            for x in v:
                if isinstance(x, dict) and x.get("id") is not None:
                    out.append(str(x["id"]))
                elif isinstance(x, (str, int, float)) and not isinstance(x, bool):
                    out.append(str(x))
            if out:
                return out
    return []


def _normalize_outfit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ids = _normalize_item_ids(r)
        if len(ids) < 2:
            continue
        reason = str(
            r.get("reasoning")
            or r.get("explanation")
            or r.get("rationale")
            or r.get("summary")
            or r.get("note")
            or ""
        ).strip()
        out.append({"item_ids": ids, "reasoning": reason})
    return out


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


def _strip_json_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```json"):
        s = s[len("```json") :].strip()
    if s.startswith("```"):
        s = s[len("```") :].strip()
    if s.endswith("```"):
        s = s[: -len("```")].strip()
    return s


def _repair_json_loose(s: str) -> str:
    """Best-effort fixes for common LLM JSON issues (trailing commas, BOM)."""
    s = s.strip().lstrip("\ufeff")
    # Smart quotes break json.loads — normalize to ASCII quotes.
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    # Remove trailing commas before } or ] (safe for typical API JSON without string edge cases).
    s = re.sub(r",(\s*[\]}])", r"\1", s)
    return s


def _json_loads_object_or_array(s: str) -> Any | None:
    """Parse JSON object or array; try lenient repair on failure."""
    s = _repair_json_loose(_strip_json_fences(s))
    for attempt in (s, _repair_json_loose(s)):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    return None


def _extract_first_json_value(s: str) -> str | None:
    """
    Extract the first balanced JSON object or array substring (string-aware).
    Handles leading prose and trailing junk after the JSON.
    """
    i = 0
    while i < len(s) and s[i] not in "{[":
        i += 1
    if i >= len(s):
        return None
    stack: list[str] = []
    in_str = False
    escape = False
    start = i
    for j in range(i, len(s)):
        c = s[j]
        if escape:
            escape = False
            continue
        if in_str:
            if c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == "{":
            stack.append("}")
        elif c == "[":
            stack.append("]")
        elif c in "}]":
            if not stack or stack[-1] != c:
                return None
            stack.pop()
            if not stack:
                return s[start : j + 1]
    return None


def _json_loads_with_balanced_fallback(s: str) -> Any | None:
    """Try full parse, then balanced extraction + parse."""
    s = s.strip()
    if not s:
        return None
    loaded = _json_loads_object_or_array(s)
    if loaded is not None:
        return loaded
    frag = _extract_first_json_value(s)
    if frag:
        return _json_loads_object_or_array(frag)
    return None


def _extract_json_array(raw: str) -> list[Any] | None:
    s = _strip_json_fences(raw)
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch != "[":
            continue
        try:
            arr, _ = dec.raw_decode(s[i:])
            if isinstance(arr, list):
                return arr
        except json.JSONDecodeError:
            continue
    # regex fallback for partial wrappers
    m = re.search(r"\[[\s\S]*\]", s)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return arr
        except Exception:
            return None
    return None


def _gemini_text_chunks(data: dict[str, Any]) -> list[str]:
    cands = data.get("candidates")
    if not isinstance(cands, list) or not cands:
        return []
    chunks: list[str] = []
    for c0 in cands:
        if not isinstance(c0, dict):
            continue
        content = c0.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for p in parts:
            if not isinstance(p, dict):
                continue
            # Do not skip "thought" parts — some Gemini builds place the JSON payload there.
            t = p.get("text")
            if isinstance(t, str) and t.strip():
                chunks.append(t.strip())
    return chunks


def _gemini_text(data: dict[str, Any]) -> str | None:
    chunks = _gemini_text_chunks(data)
    if not chunks:
        return None
    return chunks[-1]


def _parse_outfits_payload(texts: list[str]) -> list[dict[str, Any]] | None:
    _LIST_KEYS = (
        "outfits",
        "outfit_recommendations",
        "recommendations",
        "looks",
        "results",
        "data",
        "suggestions",
        "outfit_list",
    )

    def _looks_like_outfit_row(d: dict[str, Any]) -> bool:
        return len(_normalize_item_ids(d)) >= 2

    def _from_obj(x: Any) -> list[dict[str, Any]] | None:
        if isinstance(x, list):
            dict_rows = [it for it in x if isinstance(it, dict)]
            if not dict_rows:
                return None
            norm = _normalize_outfit_rows(dict_rows)
            return norm or None
        if not isinstance(x, dict):
            return None
        # Direct single-outfit object (common when top-level JSON is truncated but inner object is complete).
        direct_norm = _normalize_outfit_rows([x])
        if direct_norm:
            return direct_norm
        # Nested wrappers (LLMs often wrap JSON in "data"/"response").
        for nest in ("data", "response", "result", "payload", "output", "parsed", "json", "body"):
            nv = x.get(nest)
            if isinstance(nv, dict):
                inner = _from_obj(nv)
                if inner:
                    return inner
            if isinstance(nv, str) and nv.strip():
                loaded = _json_loads_with_balanced_fallback(nv)
                if loaded is not None:
                    inner = _from_obj(loaded)
                    if inner:
                        return inner
        if isinstance(x.get("outfit"), dict):
            norm = _normalize_outfit_rows([x["outfit"]])
            if norm:
                return norm
        for k in _LIST_KEYS:
            val = x.get(k)
            if isinstance(val, str) and val.strip():
                loaded = _json_loads_with_balanced_fallback(val)
                if loaded is not None:
                    inner = _from_obj(loaded)
                    if inner:
                        return inner
            if isinstance(val, list):
                raw = [it for it in val if isinstance(it, dict)]
                if not raw:
                    continue
                norm = _normalize_outfit_rows(raw)
                if norm:
                    return norm
        # "items" may be list of outfits or wardrobe items — only accept if rows look like outfits.
        if isinstance(x.get("items"), list):
            raw = [it for it in x.get("items", []) if isinstance(it, dict)]
            if raw and all(_looks_like_outfit_row(r) for r in raw):
                norm = _normalize_outfit_rows(raw)
                if norm:
                    return norm
        # Any list value that looks like outfit rows.
        for v in x.values():
            if isinstance(v, list):
                raw = [it for it in v if isinstance(it, dict)]
                if raw and all(_looks_like_outfit_row(r) for r in raw):
                    norm = _normalize_outfit_rows(raw)
                    if norm:
                        return norm
        return None

    def _try_parse_string(s: str) -> list[dict[str, Any]] | None:
        s = s.strip()
        if not s:
            return None
        # Whole-document JSON (often valid when responseMimeType is json).
        loaded = _json_loads_with_balanced_fallback(s)
        if loaded is not None:
            if isinstance(loaded, dict) and isinstance(loaded.get("outfits"), list) and len(loaded["outfits"]) == 0:
                return []
            rows = _from_obj(loaded)
            if rows:
                return rows
        # Brace / bracket scan (partial or extra prose).
        obj = _extract_json_object(s)
        rows = _from_obj(obj)
        if rows:
            return rows
        arr = _extract_json_array(s)
        rows = _from_obj(arr)
        if rows:
            return rows
        try:
            py_val = ast.literal_eval(_strip_json_fences(s))
            rows = _from_obj(py_val)
            if rows:
                return rows
        except Exception:
            pass
        return None

    # Try each chunk from final to initial (model often appends the JSON at the end).
    for chunk in reversed(texts):
        rows = _try_parse_string(chunk)
        if rows:
            return rows
    # Last-chance: merged text (multi-part responses).
    merged = "\n".join(texts)
    rows = _try_parse_string(merged)
    if rows:
        return rows
    return None


def _gemini_url() -> str:
    model = (settings.outfits_react_model or "").strip() or "gemini-2.0-flash"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _react_model_chain() -> list[str]:
    primary = (settings.outfits_react_model or "").strip()
    backup_raw = (settings.gemini_model or "").strip()
    backup = [m.strip() for m in backup_raw.split(",") if m.strip()]
    chain: list[str] = []
    if primary:
        chain.append(primary)
    for m in backup:
        if m not in chain:
            chain.append(m)
    if not chain:
        chain = ["gemini-2.0-flash", "gemini-2.5-flash"]
    return chain


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


async def run_llm_outfit_recommender(
    *,
    candidate: dict[str, Any],
    wardrobe_items: list[dict[str, Any]],
    color_season: str | None,
    occasion: str,
    vibe: str,
    weather_temp: int | None,
    weather_conditions: str | None,
) -> dict[str, Any]:
    """
    LLM-first outfit recommendation:
    model directly proposes full outfit item-id combinations (not tool-by-tool search).
    """
    key = (settings.gemini_api_key or "").strip()
    if not key:
        return {"success": False, "outfits": [], "reason": "missing_gemini_api_key"}

    brief = _brief_items(wardrobe_items)
    prompt = f"""You are a personal stylist.
Given a candidate purchase and a wardrobe catalog, return 4 complete outfit recommendations.

Return ONLY valid JSON in this exact shape:
{{
  "outfits": [
    {{
      "item_ids": ["wardrobe_id_1","wardrobe_id_2","wardrobe_id_3"],
      "reasoning": "One concise sentence explaining why this outfit fits weather, occasion, and vibe."
    }}
  ]
}}

Rules:
- item_ids must be copied exactly from wardrobe_items[].id (real UUID strings). Never invent or placeholder IDs.
- Prefer practical outfits for weather:
  - hot/sunny picnic => avoid heavy layers (coats, blazers, sweaters) unless absolutely needed.
  - rain => include practical footwear/layering.
- Ensure outfits match occasion and vibe.
- Keep 2 to 4 wardrobe item_ids per outfit.
- Avoid duplicate outfits.

Context:
- candidate: {json.dumps(candidate, default=str)}
- occasion: {occasion}
- vibe: {vibe}
- weather_temp: {weather_temp}
- weather_conditions: {weather_conditions}
- color_season: {color_season}
- wardrobe_items: {json.dumps(brief, default=str)}
"""

    base_gen: dict[str, Any] = {"temperature": 0.35, "maxOutputTokens": 4096}
    payload_variants: list[dict[str, Any]] = [
        {
            **base_gen,
            "responseMimeType": "application/json",
            "responseSchema": _OUTFIT_RESPONSE_SCHEMA,
        },
        {**base_gen, "responseMimeType": "application/json"},
        dict(base_gen),
    ]
    data: dict[str, Any] | None = None
    fail_reason = "request_failed"
    for model_id in _react_model_chain():
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                r = None
                for gen in payload_variants:
                    attempt_payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": gen,
                    }
                    r = await client.post(api_url, params={"key": key}, json=attempt_payload)
                    if r.status_code == 429:
                        await asyncio.sleep(1.0)
                        r = await client.post(api_url, params={"key": key}, json=attempt_payload)
                    if r.status_code != 400:
                        break
                if r is None:
                    continue
                if r.status_code == 400:
                    fail_reason = "bad_request_400"
                    continue
                if r.status_code == 429:
                    fail_reason = "rate_limited_429"
                    continue
                if r.status_code in {404, 410}:
                    fail_reason = "model_not_supported"
                    continue
                r.raise_for_status()
                raw = r.json()
                if isinstance(raw, dict):
                    data = raw
                    break
                fail_reason = "invalid_response_shape"
        except Exception:
            log.warning("LLM outfit recommender failed for model=%s", model_id, exc_info=True)
            fail_reason = "request_failed"
            continue

    if data is None:
        return {"success": False, "outfits": [], "reason": fail_reason}

    chunks = _gemini_text_chunks(data) if isinstance(data, dict) else []
    if not chunks:
        return {"success": False, "outfits": [], "reason": "no_text"}

    raw_outfits = _parse_outfits_payload(chunks)
    if raw_outfits is None:
        pf = data.get("promptFeedback") if isinstance(data, dict) else None
        log.warning(
            "LLM outfit recommender JSON parse failed; promptFeedback=%s preview=%r",
            pf,
            ("\n".join(chunks))[:1200],
        )
        return {"success": False, "outfits": [], "reason": "invalid_json"}
    if not raw_outfits:
        return {"success": False, "outfits": [], "reason": "empty_outfits"}

    items_by_id = {str(w.get("id")) for w in wardrobe_items if w.get("id") is not None}

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for cand in raw_outfits[:8]:
        if not isinstance(cand, dict):
            continue
        ids = [str(x) for x in cand.get("item_ids", []) if str(x) in items_by_id]
        # De-dup while preserving order
        uniq_ids: list[str] = []
        seen_local: set[str] = set()
        for i in ids:
            if i in seen_local:
                continue
            seen_local.add(i)
            uniq_ids.append(i)
        if len(uniq_ids) < 2:
            continue
        key_t = tuple(uniq_ids)
        if key_t in seen:
            continue
        seen.add(key_t)
        out.append(
            {
                "item_ids": uniq_ids[:4],
                "reasoning": str(cand.get("reasoning") or "").strip(),
            }
        )
        if len(out) >= 4:
            break

    if not out and raw_outfits:
        return {"success": False, "outfits": [], "reason": "no_valid_wardrobe_ids"}
    return {"success": bool(out), "outfits": out}

