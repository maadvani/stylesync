from fastapi import APIRouter, Query

from services.trends_db import get_trends_for_user

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("")
def list_trends(limit: int = Query(default=10, ge=1, le=50)):
    """
    List trends matched to the current user (MVP uses default user id).
    """
    return {"items": get_trends_for_user(limit=limit)}

