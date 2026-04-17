"""
Supabase persistence for wardrobe_items.
Expects table wardrobe_items (see schema in docs / migrations).
"""
from typing import Any

from supabase import create_client, Client

from config import settings

# For MVP without auth, use a single default user. Replace with real user_id when auth exists.
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


def _client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_key)


def insert_wardrobe_item(
    user_id: str,
    image_url: str,
    type_: str,
    primary_color: str,
    secondary_color: str | None,
    pattern: str,
    formality: int,
    seasons: list[str],
    material: str,
    style_tags: list[str],
) -> dict[str, Any] | None:
    """Insert one row; return the inserted record (with id) or None."""
    client = _client()
    if not client:
        return None
    try:
        uid = user_id or DEFAULT_USER_ID
        r = (
            client.table("wardrobe_items")
            .insert(
                {
                    "user_id": uid,
                    "image_url": image_url,
                    "type": type_,
                    "primary_color": primary_color,
                    "secondary_color": secondary_color,
                    "pattern": pattern,
                    "formality": formality,
                    "seasons": seasons,
                    "material": material,
                    "style_tags": style_tags,
                }
            )
            .execute()
        )
        if r.data and len(r.data) > 0:
            return r.data[0]
        return None
    except Exception:
        return None


def list_wardrobe_items(user_id: str | None = None) -> list[dict[str, Any]]:
    """List wardrobe items for a user, newest first."""
    client = _client()
    if not client:
        return []
    uid = user_id or DEFAULT_USER_ID
    try:
        r = (
            client.table("wardrobe_items")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .execute()
        )
        return list(r.data) if r.data else []
    except Exception:
        return []


def list_all_wardrobe_items(limit: int = 500) -> list[dict[str, Any]]:
    """
    List wardrobe items across all users, newest first.
    Used as an MVP fallback when the default user has no rows.
    """
    client = _client()
    if not client:
        return []
    try:
        r = (
            client.table("wardrobe_items")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(r.data) if r.data else []
    except Exception:
        return []


def update_wardrobe_item(
    item_id: str,
    updates: dict[str, Any],
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Update a wardrobe item (scoped to the user). Returns updated record or None.
    """
    client = _client()
    if not client:
        return None
    uid = user_id or DEFAULT_USER_ID
    safe_updates = {
        k: v
        for k, v in updates.items()
        if k
        in {
            "type",
            "primary_color",
            "secondary_color",
            "pattern",
            "formality",
            "seasons",
            "material",
            "style_tags",
        }
    }
    if not safe_updates:
        return None
    try:
        r = (
            client.table("wardrobe_items")
            .update(safe_updates)
            .eq("id", item_id)
            .eq("user_id", uid)
            .execute()
        )
        if r.data and len(r.data) > 0:
            return r.data[0]
        return None
    except Exception:
        return None


def delete_wardrobe_item(item_id: str, user_id: str | None = None) -> bool:
    """Delete a wardrobe item for the user. Returns True if a row was deleted."""
    client = _client()
    if not client:
        return False
    uid = user_id or DEFAULT_USER_ID
    try:
        r = (
            client.table("wardrobe_items")
            .delete()
            .eq("id", item_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(r.data) and len(r.data) > 0
    except Exception:
        return False


def get_wardrobe_item(item_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    """Fetch a single wardrobe item for the user."""
    client = _client()
    if not client:
        return None
    uid = user_id or DEFAULT_USER_ID
    try:
        r = (
            client.table("wardrobe_items")
            .select("*")
            .eq("id", item_id)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        if r.data and len(r.data) > 0:
            return r.data[0]
        return None
    except Exception:
        return None
