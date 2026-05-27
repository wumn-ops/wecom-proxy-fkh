"""wecom-proxy-fkh 启动入口。"""

import uvicorn

from app.config import get_settings
from app.crypto import local_ip


def main() -> None:
    settings = get_settings()
    print(f"wecom-proxy-fkh 启动: http://{settings.host}:{settings.port}")
    print("模式: API Webhook（企业微信回调加解密）")
    print(f"回调地址路径: {settings.wecom_callback_path}")
    print(f"健康检查: {settings.health_path}")
    print(f"本机 IP（内网穿透时可参考）: {local_ip()}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
