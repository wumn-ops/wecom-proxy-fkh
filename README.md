# wecom-proxy-fkh

`wecom-proxy` 的**独立副本**，用于单独部署 FKH 实例（API Webhook 模式），**不影响**其它项目。

## 与 wecom-proxy 的区别

| 项 | wecom-proxy | wecom-proxy-fkh |
|---|---|---|
| 后端端口 | 8000 | **8002** |
| 回调路径 | `/wecom/aibot/callback` | **`/wecom/aibot/callback/fkh-api`** |
| 健康检查 | `/health` | **`/health/fkh-api`** |
| H5 上传 | `/register/upload` | **`/register/upload/fkh-api`** |
| 机器人凭证 | 原机器人 | **独立 Token + EncodingAESKey** |

> 路径使用 `/fkh-api` 后缀，避免与同域下 `wecom-socket-proxy-fkh`（`/fkh` 前缀、8001 端口）冲突。

## 公网访问路径（Nginx → 8002）

与现有 `wecom.vazyme.com:8021` 共用域名，通过路径区分：

| 用途 | 公网 URL |
|------|----------|
| 健康检查 | `https://wecom.vazyme.com:8021/health/fkh-api` |
| Webhook 回调 | `https://wecom.vazyme.com:8021/wecom/aibot/callback/fkh-api` |
| H5 上传页 | `https://wecom.vazyme.com:8021/register/upload/fkh-api?token=...` |

卡片内 H5 链接由 `PUBLIC_BASE_URL` + `REGISTER_UPLOAD_PATH` 自动生成。

## Nginx 配置示例

见 [`deploy/nginx-fkh-api.conf`](deploy/nginx-fkh-api.conf)。

## 快速开始

```powershell
cd D:\aiworkspace\cursor_space\wecom-proxy-fkh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env：独立 Bot 凭证、智能表格等
python run.py
```

本地直连：`http://127.0.0.1:8002/health/fkh-api`

## 关键 .env 配置

```env
PORT=8002
WECOM_CALLBACK_PATH=/wecom/aibot/callback/fkh-api
HEALTH_PATH=/health/fkh-api
PUBLIC_BASE_URL=https://wecom.vazyme.com:8021
REGISTER_UPLOAD_PATH=/register/upload/fkh-api
```

## 功能

与 `wecom-proxy` 相同：

- URL 验证（GET）与加密回调（POST）
- 文本 / 语音 / 图文混排、模板卡片、流式消息
- 需求登记 H5 上传、智能表格写入
- 可在 `app/processor.py` 中定制 FKH 专属业务逻辑

## 项目结构

```
wecom-proxy-fkh/
├── app/
│   ├── main.py
│   ├── routes.py
│   ├── processor.py      # 可在此扩展 FKH 特定功能
│   └── ...
├── static/
├── deploy/
│   └── nginx-fkh-api.conf
├── run.py
└── requirements.txt
```
