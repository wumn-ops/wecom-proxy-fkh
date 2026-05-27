"""企业微信智能机器人主动回复（response_url）。"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

logger = logging.getLogger(__name__)


def extract_response_code_from_url(response_url: str) -> str:
    """从 response_url 查询参数中解析 response_code（若存在）。"""
    if not response_url:
        return ""
    parsed = urlparse(response_url)
    query = parse_qs(parsed.query)
    for key in ("response_code", "code"):
        values = query.get(key)
        if values and values[0]:
            return str(values[0])
    return ""


def _post_response_url(response_url: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    try:
        response = httpx.post(
            response_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("response_url 请求失败: %s payload_keys=%s", exc, list(payload.keys()))
        return False, {}
    except ValueError:
        logger.warning("response_url 响应非 JSON payload_keys=%s", list(payload.keys()))
        return False, {}

    errcode = data.get("errcode", 0)
    if errcode != 0:
        logger.warning(
            "response_url 返回 errcode=%s errmsg=%s payload_keys=%s",
            errcode,
            data.get("errmsg"),
            list(payload.keys()),
        )
        return False, data
    return True, data


def aibot_update_template_card(response_url: str, card: dict[str, Any]) -> bool:
    """尝试通过 aibot response_url 原地更新卡片（与被动回复相同格式）。"""
    if not response_url:
        return False

    ok, _ = _post_response_url(
        response_url,
        {
            "response_type": "update_template_card",
            "template_card": card,
        },
    )
    if ok:
        logger.info("aibot response_url 原地更新模板卡片成功")
    return ok


def active_send_template_card(response_url: str, card: dict[str, Any]) -> bool:
    """通过 response_url 发送一条新的模板卡片（官方文档支持的主动回复类型）。"""
    if not response_url:
        return False

    ok, _ = _post_response_url(
        response_url,
        {
            "msgtype": "template_card",
            "template_card": card,
        },
    )
    if ok:
        logger.info("主动发送模板卡片成功")
    return ok


def active_send_markdown(response_url: str, content: str) -> bool:
    """通过 response_url 发送 markdown 提示。"""
    if not response_url:
        return False

    ok, _ = _post_response_url(
        response_url,
        {
            "msgtype": "markdown",
            "markdown": {"content": content},
        },
    )
    if ok:
        logger.info("主动发送 markdown 成功")
    return ok
