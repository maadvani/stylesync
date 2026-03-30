"""
Supabase persistence for shopping_recommendations (candidate buys to score).
"""
from typing import Any

from supabase import Client, create_client

from config import settings
from services.wardrobe_db import DEFAULT_USER_ID


def _client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_key)


def list_recommendations(user_id: str | None = None) -> list[dict[str, Any]]:
    client = _client()
    if not client:
        return []
    uid = user_id or DEFAULT_USER_ID
    try:
        r = (
            client.table("shopping_recommendations")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .execute()
        )
        return list(r.data) if r.data else []
    except Exception:
        return []


def insert_recommendation(
    user_id: str | None,
    row: dict[str, Any],
) -> dict[str, Any] | None:
    client = _client()
    if not client:
        return None
    uid = user_id or DEFAULT_USER_ID
    payload = {
        "user_id": uid,
        "name": row["name"],
        "type": row["type"],
        "primary_color": row.get("primary_color"),
        "secondary_color": row.get("secondary_color"),
        "pattern": row.get("pattern") or "solid",
        "formality": int(row.get("formality") or 3),
        "seasons": row.get("seasons") or [],
        "material": row.get("material"),
        "style_tags": row.get("style_tags") or [],
        "price": row.get("price"),
        "link": row.get("link"),
        "image_url": row.get("image_url"),
    }
    try:
        ins = client.table("shopping_recommendations").insert(payload).execute()
        if ins.data and len(ins.data) > 0:
            return ins.data[0]
        return None
    except Exception:
        return None


def delete_recommendation(rec_id: str, user_id: str | None = None) -> bool:
    client = _client()
    if not client:
        return False
    uid = user_id or DEFAULT_USER_ID
    try:
        r = (
            client.table("shopping_recommendations")
            .delete()
            .eq("id", rec_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(r.data) and len(r.data) > 0
    except Exception:
        return False
