"""CRM 客户绑定 H5 路由。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.smartsheet import add_crm_bind_record
from app.upload_token import create_upload_token, verify_upload_token
from app.wecom_jssdk import build_jssdk_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["crm-bind"])
_settings = get_settings()
_BIND_BASE = _settings.crm_bind_path.rstrip("/")
_HTML_PATH = Path(__file__).resolve().parent.parent / "static" / "crm_bind.html"
_CRM_BIND_SESSION = "crm_bind"


def build_crm_bind_page_url(userid: str) -> str:
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    if not base or not userid:
        return ""
    token = create_upload_token(_CRM_BIND_SESSION, userid)
    path = settings.crm_bind_path.rstrip("/")
    return f"{base}{path}?token={token}"


class CrmBindSubmitBody(BaseModel):
    process_type: str = Field(..., pattern="^(绑定|解绑)$")
    product_code: str = Field(..., min_length=1, max_length=200)
    customer_name: str = Field(..., min_length=1, max_length=200)


def _resolve_token(token: str) -> str:
    parsed = verify_upload_token(token)
    if parsed is None:
        raise HTTPException(status_code=403, detail="链接无效或已过期，请返回企业微信重新打开")
    session_id, userid = parsed
    if session_id != _CRM_BIND_SESSION:
        raise HTTPException(status_code=403, detail="链接无效")
    return userid


@router.get(_BIND_BASE, response_class=HTMLResponse)
async def crm_bind_page(token: str = Query(...)) -> HTMLResponse:
    _resolve_token(token)
    if not _HTML_PATH.is_file():
        raise HTTPException(status_code=500, detail="绑定页面缺失")
    return HTMLResponse(_HTML_PATH.read_text(encoding="utf-8"))


@router.get(f"{_BIND_BASE}/api/jssdk-config")
async def crm_bind_jssdk_config(
    token: str = Query(...),
    url: str = Query(...),
) -> dict[str, object]:
    _resolve_token(token)
    return build_jssdk_config(url)


@router.post(f"{_BIND_BASE}/api/submit")
async def crm_bind_submit(
    body: CrmBindSubmitBody,
    token: str = Query(...),
) -> JSONResponse:
    userid = _resolve_token(token)
    ok, errmsg = add_crm_bind_record(
        process_type=body.process_type,
        product_code=body.product_code.strip(),
        customer_name=body.customer_name.strip(),
        userid=userid,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=errmsg or "写入智能表格失败")

    logger.info(
        "CRM 绑定 H5 提交成功 userid=%s type=%s product=%s customer=%s",
        userid,
        body.process_type,
        body.product_code,
        body.customer_name,
    )
    return JSONResponse({"ok": True})
