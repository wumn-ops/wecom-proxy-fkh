from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    wecom_token: str = ""
    wecom_encoding_aes_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8002
    wecom_callback_path: str = "/wecom/aibot/callback/fkh-api"
    health_path: str = "/health/fkh-api"
    log_level: str = "INFO"

    smartsheet_webhook_url: str = ""
    smartsheet_field_demand_content: str = "f9VtuW"
    smartsheet_field_image: str = "fhZuXt"
    smartsheet_field_submitter: str = "f04Gwj"
    smartsheet_field_system: str = "fJodHY"
    registration_system_options: str = "CRM,SAP,MES,其他"
    issue_list_url: str = ""

    public_base_url: str = ""
    register_upload_path: str = "/register/upload/fkh-api"
    upload_token_ttl_seconds: int = 3600
    max_upload_bytes: int = 5 * 1024 * 1024

    # 可选：配置后 H5 页可调用 ww.closeWindow() 可靠关闭（需自建应用 Secret + 可信域名）
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_corp_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
