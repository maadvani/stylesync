from __future__ import annotations

from datetime import date
from typing import Any

from supabase import Client, create_client

from config import settings
from services.wardrobe_db import DEFAULT_USER_ID


def _client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_key)


def insert_wear_log(
    *,
    item_ids: list[str],
    user_id: str | None = None,
    worn_on: date | None = None,
    source: str = "outfit_card",
) -> dict[str, Any] | None:
    client = _client()
    if not client:
        return None
    ids = [str(i).strip() for i in item_ids if str(i).strip()]
    if not ids:
        return None
    uid = user_id or DEFAULT_USER_ID
    payload = {
        "user_id": uid,
        "worn_on": (worn_on or date.today()).isoformat(),
        "item_ids": ids,
        "source": source,
    }
    try:
        r = client.table("wear_logs").insert(payload).execute()
        if r.data and len(r.data) > 0:
            return r.data[0]
        return None
    except Exception:
        return None

