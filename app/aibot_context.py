"""智能机器人 response_url 会话上下文（H5 提交后主动回复）。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from app.config import get_settings


@dataclass
class AibotContext:
    response_url: str
    chattype: str = "single"
    expires_at: float = 0.0


class AibotContextStore:
    def __init__(self) -> None:
        self._contexts: dict[str, AibotContext] = {}
        self._lock = Lock()

    def save(self, userid: str, response_url: str, *, chattype: str = "single") -> None:
        if not userid or not response_url:
            return
        ttl = get_settings().upload_token_ttl_seconds
        with self._lock:
            self._contexts[userid] = AibotContext(
                response_url=response_url,
                chattype=chattype or "single",
                expires_at=time.time() + ttl,
            )

    def take(self, userid: str) -> AibotContext | None:
        with self._lock:
            ctx = self._contexts.pop(userid, None)
        if ctx is None:
            return None
        if ctx.expires_at < time.time():
            return None
        return ctx


def remember_from_payload(payload: dict[str, Any]) -> None:
    """从企微回调 payload 保存 response_url（若存在）。"""
    response_url = payload.get("response_url")
    if not isinstance(response_url, str) or not response_url.strip():
        return
    from_info = payload.get("from") or {}
    userid = from_info.get("userid")
    if not isinstance(userid, str) or not userid:
        return
    chattype = str(payload.get("chattype") or "single")
    aibot_context_store.save(userid, response_url.strip(), chattype=chattype)


aibot_context_store = AibotContextStore()
