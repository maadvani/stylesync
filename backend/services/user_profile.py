"""Get/set user profile (e.g. color_season from quiz). MVP: default user only."""
from typing import Any

from supabase import create_client

from config import settings

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def _client():
    if not settings.supabase_url or not settings.supabase_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_key)


def get_color_season(user_id: str | None = None) -> str | None:
    uid = user_id or DEFAULT_USER_ID
    client = _client()
    if not client:
        return None
    try:
        r = client.table("user_profiles").select("color_season").eq("user_id", uid).execute()
        if r.data and len(r.data) > 0 and r.data[0].get("color_season"):
            return r.data[0]["color_season"]
        return None
    except Exception:
        return None


def set_color_season(color_season: str, user_id: str | None = None) -> bool:
    uid = user_id or DEFAULT_USER_ID
    client = _client()
    if not client:
        return False
    try:
        from datetime import datetime, timezone
        row = {"user_id": uid, "color_season": color_season, "updated_at": datetime.now(timezone.utc).isoformat()}
        client.table("user_profiles").upsert(row, on_conflict="user_id").execute()
        return True
    except Exception:
        return False
