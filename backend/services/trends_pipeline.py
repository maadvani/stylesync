"""
Trend intelligence pipeline (manual/local run).

Goal: scrape a small set of sources, extract trend candidates with Groq (JSON-only),
cluster candidates with local embeddings + HDBSCAN, then store clustered trends in Supabase.

This module is designed to be called by a local script (definitely-free MVP).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import hdbscan
import numpy as np
from sentence_transformers import SentenceTransformer
from groq import Groq

from config import settings
from services.trends_db import _client


try:
    from crawl4ai import AsyncWebCrawler  # preferred import in this environment
except Exception:  # pragma: no cover
    AsyncWebCrawler = None  # type: ignore


GROQ_TRENDS_MODEL = "llama-3.3-70b-versatile"


DEFAULT_SOURCES: dict[str, str] = {
    # MVP: women-focused sources only.
    "vogue_trends": "https://www.vogue.com/fashion/trends",
    "harpers_bazaar_trends": "https://www.harpersbazaar.com/fashion/trends/",
    "whowhatwear_trends": "https://www.whowhatwear.com/fashion-trends",
    "refinery_trends": "https://www.refinery29.com/en-us/fashion/trends",
    "elle_women_trends": "https://www.elle.com/fashion/trend-reports/",
    "instyle_womens_fashion": "https://www.instyle.com/fashion",
}


@dataclass
class TrendCandidate:
    title: str
    description: str | None
    keywords: list[str]
    dominant_colors: list[str]


BANNED_TITLE_TERMS = {
    "male",
    "men",
    "mens",
    "grooming",
    "celebrity",
    "eco",
    "sustainable",
    "practical",
    "high end",
    "luxury",
    "seasonal style",
    "style tips",
    "fashion week coverage",
}


def _is_low_signal_candidate(c: TrendCandidate) -> bool:
    """
    Filter out generic/meta topics that are not specific women's style trends.
    """
    t = c.title.lower().strip()
    d = (c.description or "").lower()
    text = f"{t} {d}"
    if any(term in text for term in BANNED_TITLE_TERMS):
        return True
    # Titles that are too short/generic usually aren't useful trend clusters.
    if len(t.split()) < 2:
        return True
    too_generic = [
        "style",
        "fashion",
        "chic",
        "trend",
        "latest",
        "look",
    ]
    if t in too_generic:
        return True
    return False


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json") :].strip()
    if text.startswith("```"):
        text = text[len("```") :].strip()
    if text.endswith("```"):
        text = text[: -len("```")].strip()
    return text


def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
    text = _strip_json_fences(text)
    # Extract first JSON array
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        text = match.group(0)
    try:
        arr = json.loads(text)  # type: ignore[name-defined]
    except Exception:
        return None
    if not isinstance(arr, list):
        return None
    out: list[dict[str, Any]] = []
    for item in arr:
        if isinstance(item, dict):
            out.append(item)
    return out


def _groq_extract_trend_candidates(page_text: str, max_trends: int = 6) -> list[TrendCandidate]:
    if not settings.groq_api_key:
        return []

    client = Groq(api_key=settings.groq_api_key)

    prompt = f"""You are a women's fashion trend researcher.
Extract up to {max_trends} CURRENT, SPECIFIC women-focused style trends from the following page content.

Return ONLY a JSON array (no markdown, no explanation). Each array element must be:
{{
  "title": string (2-6 words, specific style name),
  "description": string (1 short sentence describing silhouette/fabric/styling),
  "keywords": string[] (max 6 short keywords, garment-oriented),
  "dominant_colors": string[] (max 6 color names, e.g. camel, cream, navy, ruby; avoid 'neutral')
}}

Rules:
- ONLY women-centric fashion trends.
- Prefer concrete style trends like "Office Siren Tailoring", "Sheer Layering", "Quiet Luxury Neutrals", "Balletcore", "Coastal Grandmother", "Boho Revival", "Y2K Denim", "Romantic Lace Slip".
- Exclude generic/meta topics: celebrity news, male style, sustainability overviews, broad "luxury", broad "practical fashion", broad "seasonal style".
- Title must be trend-like and not generic ("Fashion", "Style", "Latest Trends" are invalid).

CONTENT (truncate as needed):
{page_text[:12000]}
"""
    r = client.chat.completions.create(
        model=GROQ_TRENDS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=800,
    )
    text = (r.choices[0].message.content or "").strip()
    if not text:
        return []
    # Parse JSON array
    text = _strip_json_fences(text)
    try:
        arr = json.loads(text)  # type: ignore[name-defined]
    except Exception:
        # Fallback: strip to first array
        m = re.search(r"\\[[\\s\\S]*\\]", text)
        if not m:
            return []
        try:
            arr = json.loads(m.group(0))
        except Exception:
            return []
    if not isinstance(arr, list):
        return []

    candidates: list[TrendCandidate] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        desc = item.get("description")
        keywords = item.get("keywords") or []
        colors = item.get("dominant_colors") or []
        if not isinstance(keywords, list):
            keywords = []
        if not isinstance(colors, list):
            colors = []
        candidates.append(
            TrendCandidate(
                title=title,
                description=str(desc) if desc else None,
                keywords=[str(k).strip().lower() for k in keywords if str(k).strip()],
                dominant_colors=[str(c).strip().lower() for c in colors if str(c).strip()],
            )
        )
    filtered = [c for c in candidates if not _is_low_signal_candidate(c)]
    return filtered


def _groq_cluster_label(candidates: list[TrendCandidate]) -> dict[str, str]:
    if not settings.groq_api_key:
        return {"name": "Trend Cluster", "description": ""}
    client = Groq(api_key=settings.groq_api_key)

    sample = candidates[:10]
    bullets = "\n".join([f"- {c.title}: {c.description or ''}" for c in sample])
    prompt = f"""Given these women's fashion trend candidates, create a highly specific trend label and short description.

Return ONLY valid JSON:
{{"name":"...","description":"..."}}

Rules:
- Name must be 2-4 words.
- Name should sound like a concrete women's style trend (not generic).
- Avoid words like: "style", "fashion", "high end", "practical", "seasonal", "male celebrity".
- Description should mention key garment silhouettes or materials.

CANDIDATES:
{bullets}
"""
    r = client.chat.completions.create(
        model=GROQ_TRENDS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=200,
    )
    text = (r.choices[0].message.content or "").strip()
    text = _strip_json_fences(text)
    try:
        obj = json.loads(text)  # type: ignore[name-defined]
    except Exception:
        return {"name": "Trend Cluster", "description": ""}
    if not isinstance(obj, dict):
        return {"name": "Trend Cluster", "description": ""}
    name = (obj.get("name") or "Trend Cluster").strip()
    desc = (obj.get("description") or "").strip()
    return {"name": name, "description": desc}


def _embed_texts(texts: list[str]) -> np.ndarray:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    emb = model.encode(texts, normalize_embeddings=True)
    return np.array(emb, dtype=np.float32)


def _cluster_candidates(candidates: list[TrendCandidate]) -> list[list[int]]:
    """
    Returns clusters as lists of candidate indices.
    """
    if len(candidates) < 3:
        return [list(range(len(candidates)))]

    texts = [f"{c.title}. {c.description or ''}. {' '.join(c.keywords)}" for c in candidates]
    emb = _embed_texts(texts)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1, metric="euclidean")
    labels = clusterer.fit_predict(emb)

    clusters: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels.tolist()):
        if lab == -1:
            continue
        clusters.setdefault(int(lab), []).append(idx)

    # If everything is noise, treat all as one cluster.
    if not clusters:
        return [list(range(len(candidates)))]

    return list(clusters.values())


def run_scrape_and_store_trends(
    sources: dict[str, str] | None = None,
    max_candidates_per_source: int = 6,
    max_clusters_to_store: int = 20,
) -> list[dict[str, Any]]:
    """
    Manual/local run: scrape → extract candidates → cluster → store in Supabase.
    """
    if AsyncWebCrawler is None:
        raise RuntimeError(
            "crawl4ai is installed but AsyncWebCrawler is unavailable. "
            "Run `pip install -r requirements.txt` in backend and retry."
        )
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY missing in backend/.env")

    sources = sources or DEFAULT_SOURCES

    all_candidates: list[TrendCandidate] = []

    async def _scrape_all() -> None:
        nonlocal all_candidates
        async with AsyncWebCrawler() as crawler:
            for name, url in sources.items():
                try:
                    res = await crawler.arun(url)
                    # Pull a best-effort content field
                    page_text = ""
                    for attr in ["extracted_content", "cleaned_html", "markdown", "html"]:
                        if hasattr(res, attr):
                            page_text = getattr(res, attr) or ""
                            if page_text:
                                break
                    if not page_text:
                        continue
                    candidates = _groq_extract_trend_candidates(
                        page_text, max_trends=max_candidates_per_source
                    )
                    all_candidates.extend(candidates)
                except Exception:
                    continue

    import asyncio

    asyncio.run(_scrape_all())

    if not all_candidates:
        return []

    clusters = _cluster_candidates(all_candidates)

    # Store clustered trends
    client = _client()
    if not client:
        return []

    total = len(all_candidates)
    stored: list[dict[str, Any]] = []
    for cluster_id, idxs in enumerate(clusters):
        if len(stored) >= max_clusters_to_store:
            break
        members = [all_candidates[i] for i in idxs]

        merged_keywords: list[str] = []
        merged_colors: list[str] = []
        for m in members:
            merged_keywords.extend(m.keywords)
            merged_colors.extend(m.dominant_colors)

        # De-dup while preserving order
        def _uniq(xs: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for x in xs:
                if x in seen:
                    continue
                seen.add(x)
                out.append(x)
            return out

        merged_keywords = _uniq(merged_keywords)[:12]
        merged_colors = _uniq(merged_colors)[:8]

        label = _groq_cluster_label(members)
        size = len(members)
        velocity = round(size / max(total, 1), 3)

        row = {
            "name": label["name"],
            "description": label.get("description", ""),
            "keywords": merged_keywords,
            "dominant_colors": merged_colors,
            "size": size,
            "velocity": velocity,
            "cluster_id": cluster_id,
        }

        try:
            r = client.table("trends").insert(row).execute()
            if r.data and len(r.data) > 0:
                stored.append(r.data[0])
        except Exception:
            continue

    return stored

