from __future__ import annotations

import logging
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.config import get_settings
from app.crypto import WeComCrypto, WeComCryptoError, random_nonce
from app.processor import MessageProcessor

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()
_processor = MessageProcessor()


def _get_crypto() -> WeComCrypto:
    settings = get_settings()
    if not settings.wecom_token or not settings.wecom_encoding_aes_key:
        raise HTTPException(
            status_code=500,
            detail="请在 .env 中配置 WECOM_TOKEN 与 WECOM_ENCODING_AES_KEY",
        )
    return WeComCrypto(
        token=settings.wecom_token,
        encoding_aes_key=settings.wecom_encoding_aes_key,
        receive_id="",
    )


@router.get(settings.health_path)
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "webhook"}


@router.get(settings.wecom_callback_path)
async def verify_callback(
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
) -> Response:
    """企业微信保存 API 配置时的 URL 验证。"""
    crypto = _get_crypto()
    try:
        plain = crypto.verify_url(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echo_str=unquote(echostr),
        )
    except WeComCryptoError as exc:
        logger.error("URL 验证失败: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    logger.info("URL 验证成功")
    return Response(content=plain, media_type="text/plain")


@router.post(settings.wecom_callback_path)
async def receive_callback(
    request: Request,
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(...),
    nonce: str = Query(...),
) -> Response:
    """接收企业微信智能机器人加密回调，加工后被动回复。"""
    crypto = _get_crypto()
    body = await request.body()

    try:
        payload = crypto.decrypt_callback(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            post_data=body,
        )
    except WeComCryptoError as exc:
        logger.error("回调解密失败: %s", exc)
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    logger.info("收到回调: msgtype=%s msgid=%s", payload.get("msgtype"), payload.get("msgid"))
    logger.debug("明文 payload: %s", payload)

    reply = _processor.handle(payload)

    if reply is None:
        return Response(content="", media_type="text/plain")

    encrypted = crypto.encrypt_reply(reply, nonce=nonce)
    return Response(content=_json_dumps(encrypted), media_type="application/json")


def _json_dumps(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
