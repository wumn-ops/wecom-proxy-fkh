"""通过企业微信应用 API 原地更新模板卡片（需 response_code）。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.wecom_jssdk import get_jssdk_signer

logger = logging.getLogger(__name__)

_QYAPI = "https://qyapi.weixin.qq.com/cgi-bin/message/update_template_card"


def corp_update_template_card(
    response_code: str,
    card: dict[str, Any],
    *,
    userid: str = "",
) -> tuple[bool, int, str]:
    """使用 response_code 原地更新已发送的模板卡片（不消耗 response_url）。"""
    settings = get_settings()
    if not response_code:
        return False, 0, "missing_response_code"
    if not settings.wecom_corp_secret or not settings.wecom_agent_id:
        logger.info("未配置 WECOM_CORP_SECRET/AGENT_ID，跳过 corp 卡片更新")
        return False, 0, "corp_not_configured"

    signer = get_jssdk_signer()
    if signer is None:
        return False, 0, "signer_unavailable"

    try:
        access_token = signer.get_access_token()
    except Exception as exc:
        logger.warning("获取 access_token 失败: %s", exc)
        return False, 0, "access_token_failed"

    attempts: list[dict[str, Any]] = [
        {
            "agentid": int(settings.wecom_agent_id),
            "response_code": response_code,
            "template_card": card,
        },
    ]
    if userid:
        attempts.append(
            {
                "agentid": int(settings.wecom_agent_id),
                "response_code": response_code,
                "template_card": card,
                "userids": [userid],
            }
        )

    last_errcode = 0
    last_errmsg = ""
    for payload in attempts:
        try:
            response = httpx.post(
                _QYAPI,
                params={"access_token": access_token},
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("corp 更新模板卡片请求失败: %s", exc)
            return False, 0, "http_error"
        except ValueError:
            logger.warning("corp 更新模板卡片响应非 JSON")
            return False, 0, "invalid_json"

        errcode = int(data.get("errcode", 0))
        last_errmsg = str(data.get("errmsg") or "")
        if errcode == 0:
            logger.info("corp 原地更新模板卡片成功")
            return True, 0, "ok"

        last_errcode = errcode
        logger.warning(
            "corp 更新模板卡片 errcode=%s errmsg=%s has_userids=%s",
            errcode,
            last_errmsg,
            "userids" in payload,
        )

    return False, last_errcode, last_errmsg
