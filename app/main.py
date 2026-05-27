import logging

from fastapi import FastAPI

from app.config import get_settings
from app.routes import router
from app.crm_bind_routes import router as crm_bind_router
from app.upload_routes import router as upload_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="wecom-proxy-fkh",
    description="企业微信智能机器人 API 模式 Webhook 代理（FKH 独立实例）",
    version="0.1.0",
)

app.include_router(router)
app.include_router(crm_bind_router)
app.include_router(upload_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "wecom-proxy-fkh",
        "mode": "webhook",
        "callback": settings.wecom_callback_path,
        "health": settings.health_path,
        "crm_bind": settings.crm_bind_path,
        "register_upload": settings.register_upload_path,
    }
