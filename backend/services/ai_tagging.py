"""
AI tagging: image → caption (HF Inference API) → structured JSON (Groq).
- Strong JSON-only prompt, strip code fences, retry once, fallback to defaults.
"""
import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx
from groq import Groq

from config import settings

# Hugging Face: use a model that returns a single caption (BLIP2 is reliable on free tier).
# Florence-2 on serverless may require different payload; we can add it later.
HF_CAPTION_MODEL = "Salesforce/blip2-opt-2.7b-coco"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_CAPTION_MODEL}"

# Defaults when parsing fails or LLM doesn't return valid JSON
DEFAULT_ATTRIBUTES = {
    "type": "top",
    "primary_color": "neutral",
    "secondary_color": None,
    "pattern": "solid",
    "formality": 3,
    "seasons": ["spring", "summer", "fall", "winter"],
    "material": "unknown",
    "style_tags": ["casual"],
}

GEMINI_MAX_INLINE_BYTES = 7 * 1024 * 1024  # 7MB inline limit commonly enforced
_EXAMPLE_DIR = Path(__file__).resolve().parent / "few_shot_examples"
_MIME_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}

# Hybrid few-shot: same code path as generic few-shot, but pick images for *your* failure cases.
# Put files under few_shot_examples/ (or use an absolute path). Missing files are skipped.
# Edit this list when you log a bad tag: save that photo here, set JSON to the correct labels, restart backend.
FEW_SHOT_EXAMPLES: list[tuple[str, str]] = [
    (
        "edge_slipdress.jpg",
        '{"type":"dress","primary_color":"ivory","secondary_color":null,"pattern":"solid","formality":3,"seasons":["spring","summer"],"material":"satin","style_tags":["romantic","minimal","trendy"]}',
    ),
    (
        "edge_longblazer.jpg",
        '{"type":"blazer","primary_color":"black","secondary_color":null,"pattern":"solid","formality":4,"seasons":["fall","winter","spring"],"material":"wool blend","style_tags":["classic","formal","preppy"]}',
    ),
    (
        "edge_shacket.jpg",
        '{"type":"jacket","primary_color":"tan","secondary_color":null,"pattern":"solid","formality":2,"seasons":["fall","spring"],"material":"cotton","style_tags":["casual","trendy","classic"]}',
    ),
]


def _load_example(filename: str) -> tuple[str, str] | None:
    """
    Load a few-shot example image and return (base64, mime_type).
    Returns None when file is missing/unreadable.
    """
    raw_path = Path(filename)
    path = raw_path if raw_path.is_absolute() else (_EXAMPLE_DIR / filename)
    if not path.exists() or not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except Exception:
        return None
    ext = path.suffix.lower().lstrip(".")
    mime = _MIME_BY_EXT.get(ext, "image/jpeg")
    return base64.b64encode(raw).decode("utf-8"), mime


def _preload_few_shot_turns() -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for filename, expected_json in FEW_SHOT_EXAMPLES:
        loaded = _load_example(filename)
        if loaded is None:
            continue
        ex_b64, ex_mime = loaded
        turns.append(
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": ex_mime, "data": ex_b64}},
                    {"text": "Tag this item."},
                ],
            }
        )
        turns.append({"role": "model", "parts": [{"text": expected_json}]})
    return turns


_FEW_SHOT_TURNS = _preload_few_shot_turns()


def _build_few_shot_contents(prompt: str, b64: str, mime_type: str) -> list[dict[str, Any]]:
    """
    Build Gemini multi-turn conversation with optional few-shot examples.
    """
    contents: list[dict[str, Any]] = [
        {"role": "user", "parts": [{"text": prompt}]},
        {
            "role": "model",
            "parts": [{"text": "Understood. I will return only valid JSON following the requested schema."}],
        },
    ]

    if _FEW_SHOT_TURNS:
        contents.extend(_FEW_SHOT_TURNS)

    contents.append(
        {
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": b64}},
                {"text": "Tag this item."},
            ],
        }
    )
    return contents


def _gemini_primary_model_url() -> str:
    raw = (getattr(settings, "gemini_model", None) or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    mid = parts[0] if parts else "gemini-2.5-flash"
    return f"https://generativelanguage.googleapis.com/v1beta/models/{mid}:generateContent"


def get_caption(image_bytes: bytes) -> str | None:
    """Get one-line image caption from Hugging Face Inference API."""
    if not settings.hf_token:
        return None
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {settings.hf_token}"},
                content=image_bytes,
            )
            r.raise_for_status()
            data = r.json()
            # BLIP2 returns list of dicts with "generated_text" or similar
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("generated_text") or str(data[0])
            if isinstance(data, dict):
                return data.get("generated_text") or data.get("caption") or ""
            return str(data) if data else None
    except Exception:
        return None


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences so we can parse JSON."""
    text = text.strip()
    for prefix in ("```json", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return text


def _parse_and_validate(raw: str) -> dict[str, Any] | None:
    """Parse JSON and validate required fields; return None if invalid."""
    raw = _strip_json_fences(raw)
    # Try to extract a JSON object if there's extra text
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(out, dict):
        return None
    # Normalize formality to 1–5
    f = out.get("formality")
    if f is not None:
        try:
            f = int(f)
            out["formality"] = max(1, min(5, f))
        except (TypeError, ValueError):
            out["formality"] = DEFAULT_ATTRIBUTES["formality"]
    else:
        out["formality"] = DEFAULT_ATTRIBUTES["formality"]
    # Ensure type exists
    if not out.get("type") or not str(out["type"]).strip():
        out["type"] = DEFAULT_ATTRIBUTES["type"]
    if not out.get("primary_color") or not str(out["primary_color"]).strip():
        out["primary_color"] = DEFAULT_ATTRIBUTES["primary_color"]
    if "seasons" not in out or not isinstance(out["seasons"], list):
        out["seasons"] = DEFAULT_ATTRIBUTES["seasons"]
    if "style_tags" not in out or not isinstance(out["style_tags"], list):
        out["style_tags"] = DEFAULT_ATTRIBUTES["style_tags"]
    return out


def _groq_caption_to_json(caption: str) -> dict[str, Any] | None:
    """Ask Groq to turn caption into our schema. JSON only, no markdown."""
    if not settings.groq_api_key:
        return None
    client = Groq(api_key=settings.groq_api_key)
    prompt = f"""You are a fashion attribute extractor. Given a short description of a clothing item, output ONLY a single valid JSON object with these exact keys. No other text, no markdown, no code block.

Description: {caption}

Output exactly this structure (use null where not applicable):
{{"type": "shirt|pants|dress|jacket|coat|shoes|skirt|sweater|blouse|t-shirt|etc", "primary_color": "specific color e.g. navy blue, beige", "secondary_color": null or a second color, "pattern": "solid|stripes|floral|geometric|plaid|etc", "formality": 1-5 (1=gym, 2=casual, 3=smart casual, 4=business, 5=formal), "seasons": ["spring","summer","fall","winter"], "material": "cotton|wool|silk|etc", "style_tags": ["minimal","classic","trendy", etc]}}"""

    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400,
        )
        text = (r.choices[0].message.content or "").strip()
        return _parse_and_validate(text)
    except Exception:
        return None


def recognize_clothing(image_bytes: bytes) -> dict[str, Any]:
    """
    Run full pipeline: HF caption → Groq JSON. Retry once on parse failure; then fallback to defaults.
    """
    caption = get_caption(image_bytes)
    if not caption:
        caption = "A clothing item."
    # First attempt
    attrs = _groq_caption_to_json(caption)
    if attrs is not None:
        return attrs
    # Retry once
    attrs = _groq_caption_to_json(caption)
    if attrs is not None:
        return attrs
    # Fallback
    return dict(DEFAULT_ATTRIBUTES)


def _gemini_image_to_json(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    targets: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Use Gemini (vision) to extract wardrobe attributes directly from the image.
    Returns parsed/validated dict or None.
    """
    if not settings.gemini_api_key:
        return None
    if len(image_bytes) > GEMINI_MAX_INLINE_BYTES:
        # Too large for inline; fall back to caption pipeline.
        return None

    targets = [t.strip().lower() for t in (targets or []) if t and t.strip()]
    targets_clause = (
        "User intends to catalog these target item(s): "
        + ", ".join(targets)
        + "."
        if targets
        else "User did not specify a target item."
    )

    prompt = f"""You are a wardrobe cataloging system. Analyze the clothing item in this image and return a JSON object.

Return ONLY valid JSON. No markdown. No explanation. No extra keys.

{targets_clause}

If target item(s) are provided:
- Output one wardrobe JSON per target item, in the same order as targets, inside: {{ "items": [ ... ] }}.
- Ignore non-target garments.

If multiple garments are visible, tag the single most prominent one (the "hero" item a shopper would click on).

Schema:
{{
  "type": "top|t-shirt|shirt|blouse|sweater|jacket|coat|blazer|dress|skirt|pants|jeans|shorts|shoes|bag|accessory|other",
  "primary_color": "<specific color, e.g. ivory, navy, forest green — never 'neutral'>",
  "secondary_color": "<specific color or null>",
  "pattern": "solid|stripes|floral|geometric|plaid|polka_dot|animal_print|graphic|other",
  "formality": <1=gym, 2=casual, 3=smart casual, 4=business, 5=formal>,
  "seasons": ["spring","summer","fall","winter"],
  "material": "<fabric name or 'unknown'>",
  "style_tags": ["<tags from: minimal|classic|trendy|romantic|bohemian|streetwear|preppy|athleisure|formal|casual>"]
}}

Fill every field. Use null only for secondary_color."""

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": _build_few_shot_contents(prompt, b64, mime_type),
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512,
        },
    }

    try:
        with httpx.Client(timeout=45.0) as client:
            r = client.post(
                _gemini_primary_model_url(),
                params={"key": settings.gemini_api_key},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            # Typical shape: { candidates: [ { content: { parts: [ { text: "..." } ] } } ] }
            texts: list[str] = []
            candidates = data.get("candidates") if isinstance(data, dict) else None
            if candidates and isinstance(candidates, list) and candidates[0]:
                content = candidates[0].get("content")
                parts = content.get("parts") if isinstance(content, dict) else None
                if parts and isinstance(parts, list):
                    for p in parts:
                        if not isinstance(p, dict):
                            continue
                        if p.get("thought") is True:
                            continue
                        t = p.get("text")
                        if isinstance(t, str) and t.strip():
                            texts.append(t.strip())
            if not texts:
                return None
            # Final part is usually the JSON answer after optional thought parts.
            for chunk in reversed(texts):
                try:
                    return json.loads(_strip_json_fences(chunk))
                except json.JSONDecodeError:
                    continue
            return None
    except Exception:
        return None


def recognize_clothing_gemini(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict[str, Any]:
    """
    Gemini-first tagging: retry once, then fall back to the HF+Groq pipeline, then defaults.
    """
    attrs = _gemini_image_to_json(image_bytes, mime_type=mime_type)
    if attrs is not None:
        return attrs
    attrs = _gemini_image_to_json(image_bytes, mime_type=mime_type)
    if attrs is not None:
        return attrs
    # Fall back to existing pipeline (caption → Groq)
    return recognize_clothing(image_bytes)


def recognize_clothing_gemini_multi(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    targets: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Gemini-first tagging for multiple target items.
    Returns a list of validated attribute dicts (length >= 1).
    """
    raw = _gemini_image_to_json(image_bytes, mime_type=mime_type, targets=targets)
    # Retry once if we got something but can't validate into a list.
    if raw is None:
        raw = _gemini_image_to_json(image_bytes, mime_type=mime_type, targets=targets)
    if raw is None:
        return [recognize_clothing(image_bytes)]

    # If Gemini returned {"items": [...]}
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        out: list[dict[str, Any]] = []
        for item in raw["items"]:
            if not isinstance(item, dict):
                continue
            validated = _parse_and_validate(json.dumps(item))
            if validated:
                out.append(validated)
        return out if out else [recognize_clothing(image_bytes)]

    # If Gemini returned a single object
    if isinstance(raw, dict):
        validated = _parse_and_validate(json.dumps(raw))
        return [validated] if validated else [recognize_clothing(image_bytes)]

    return [recognize_clothing(image_bytes)]


def recognize_clothing_from_url(image_url: str) -> dict[str, Any]:
    """
    Download image bytes from a URL (e.g. Cloudinary) and run recognize_clothing.
    """
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(image_url)
            r.raise_for_status()
            return recognize_clothing(r.content)
    except Exception:
        return dict(DEFAULT_ATTRIBUTES)


def recognize_clothing_from_url_gemini(image_url: str) -> dict[str, Any]:
    """
    Download image bytes from a URL and run Gemini-first tagging.
    """
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            r = client.get(image_url)
            r.raise_for_status()
            mime = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return recognize_clothing_gemini(r.content, mime_type=mime)
    except Exception:
        return dict(DEFAULT_ATTRIBUTES)


def recognize_clothing_from_url_gemini_multi(image_url: str, targets: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Download image bytes from a URL and run Gemini-first multi-target tagging.
    """
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            r = client.get(image_url)
            r.raise_for_status()
            mime = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return recognize_clothing_gemini_multi(r.content, mime_type=mime, targets=targets)
    except Exception:
        return [dict(DEFAULT_ATTRIBUTES)]
