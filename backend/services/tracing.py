"""
LangSmith tracing helpers with safe no-op fallback.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from config import settings

_ENABLED = bool(settings.langsmith_tracing and settings.langsmith_api_key)

if _ENABLED:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    if settings.langsmith_project:
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    if settings.langsmith_endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)

try:
    if _ENABLED:
        from langsmith import traceable as _ls_traceable
    else:
        _ls_traceable = None
except Exception:
    _ls_traceable = None


def traceable(
    name: str,
    *,
    run_type: str = "chain",
    tags: list[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Wrap a function for LangSmith tracing when enabled.
    Falls back to identity decorator when LangSmith is unavailable.
    """

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _ls_traceable is None:
            return fn
        return _ls_traceable(name=name, run_type=run_type, tags=tags or [])(fn)

    return _decorator

