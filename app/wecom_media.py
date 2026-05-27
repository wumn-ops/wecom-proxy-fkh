"""企业微信智能机器人媒体下载与解密。"""

from __future__ import annotations

import base64
import logging
from functools import lru_cache

import httpx

from app.config import get_settings
from app.crypto import WeComCrypto, WeComCryptoError

logger = logging.getLogger(__name__)


@lru_cache
def _get_crypto() -> WeComCrypto:
    settings = get_settings()
    return WeComCrypto(
        token=settings.wecom_token,
        encoding_aes_key=settings.wecom_encoding_aes_key,
        receive_id="",
    )


def download_decrypted_image(url: str) -> tuple[bool, bytes | str]:
    """下载并解密用户发送的图片，返回 (成功, 二进制数据或错误信息)。"""
    url = url.strip()
    if not url:
        return False, "图片 URL 为空"

    try:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        plain = _get_crypto().decrypt_media(response.content)
    except httpx.HTTPError as exc:
        logger.exception("下载图片失败 url=%s", url[:80])
        return False, f"下载失败: {exc}"
    except WeComCryptoError as exc:
        logger.exception("解密图片失败 url=%s", url[:80])
        return False, str(exc)

    if not plain:
        return False, "图片内容为空"
    return True, plain


def prepare_smartsheet_images(urls: list[str]) -> tuple[list[dict[str, str]], str]:
    """将加密图片 URL 转为智能表格 image_base64 格式。"""
    images: list[dict[str, str]] = []
    for index, url in enumerate(urls, start=1):
        ok, result = download_decrypted_image(url)
        if not ok:
            return [], f"图片{index}处理失败: {result}"
        assert isinstance(result, bytes)
        images.append(
            {
                "title": f"图片{index}",
                "image_base64": base64.b64encode(result).decode("ascii"),
            }
        )
    return images, ""
