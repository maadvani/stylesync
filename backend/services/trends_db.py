"""
Supabase persistence + matching logic for trend intelligence MVP.
"""

from __future__ import annotations

from typing import Any

from supabase import create_client, Client

from config import settings

from services import wardrobe_db, user_profile, utility_score

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def _client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_key)


def list_trends() -> list[dict[str, Any]]:
    client = _client()
    if not client:
        return []
    try:
        r = client.table("trends").select("*").order("last_updated", desc=True).limit(50).execute()
        return list(r.data) if r.data else []
    except Exception:
        return []


def upsert_user_trend_match(user_id: str, trend_id: str, match_score: float, wardrobe_coverage: float) -> None:
    client = _client()
    if not client:
        return
    try:
        client.table("user_trend_matches").upsert(
            {
                "user_id": user_id,
                "trend_id": trend_id,
                "match_score": match_score,
                "wardrobe_coverage": wardrobe_coverage,
            },
            on_conflict="(user_id,trend_id)",
        ).execute()
    except Exception:
        # Cache is optional; failures shouldn't break the UI.
        return


def _dominant_color_match_score(color_season: str | None, dominant_colors: list[str] | None) -> float:
    if not dominant_colors:
        return 0.5
    scores = []
    for c in dominant_colors:
        if not c:
            continue
        scores.append(utility_score._color_match_score(color_season, c))
    return round(sum(scores) / max(len(scores), 1), 2)


def _wardrobe_coverage(user_items: list[dict[str, Any]], dominant_colors: list[str] | None) -> float:
    if not user_items:
        return 0.0
    dominant = [d.lower() for d in (dominant_colors or []) if isinstance(d, str) and d.strip()]
    if not dominant:
        return 0.0
    match = 0
    for it in user_items:
        pc = (it.get("primary_color") or "").lower()
        if any(d in pc or pc in d for d in dominant):
            match += 1
    return round(match / len(user_items), 3)


def get_trends_for_user(limit: int = 10) -> list[dict[str, Any]]:
    """
    Returns trends with computed match_score + wardrobe_coverage for the user.
    Also writes these values to user_trend_matches as a cache.
    """
    client = _client()
    if not client:
        return []

    color_season = user_profile.get_color_season(DEFAULT_USER_ID)  # MVP default user
    user_items = wardrobe_db.list_wardrobe_items(DEFAULT_USER_ID)

    trends = list_trends()
    scored: list[dict[str, Any]] = []

    for t in trends:
        dominant_colors = t.get("dominant_colors") or []
        match_score = _dominant_color_match_score(color_season, dominant_colors)
        wardrobe_coverage = _wardrobe_coverage(user_items, dominant_colors)

        # Combine: higher match + better coverage gets higher ordering.
        combined = round(match_score * 0.7 + wardrobe_coverage * 0.3, 2)

        scored.append(
            {
                **t,
                "match_score": combined,
                "wardrobe_coverage": wardrobe_coverage,
            }
        )

        upsert_user_trend_match(DEFAULT_USER_ID, t["id"], match_score, wardrobe_coverage)

    scored.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return scored[:limit]

