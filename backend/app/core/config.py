"""應用設定。變數清單與 specs/001-diet-log-mvp/quickstart.md 一致。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- 資料庫 ---
    database_url: str = "postgresql+psycopg://caluli:caluli@localhost:5432/caluli"

    # --- 會話 ---
    # 長度須 ≥ 32 bytes：低於此值 PyJWT 會對 HMAC-SHA256 發出
    # InsecureKeyLengthWarning（RFC 7518 §3.2）。正式環境務必覆寫。
    jwt_secret: str = "dev-only-insecure-secret-please-override-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_seconds: int = 604800  # 7 天，見 research.md R-04

    # --- LINE Login ---
    # 兩個入口共用同一組 channel 設定；驗證邏輯不因入口分岔（憲章原則 I）。
    line_channel_id: str = ""
    line_channel_secret: str = ""
    line_token_endpoint: str = "https://api.line.me/oauth2/v2.1/token"
    line_verify_endpoint: str = "https://api.line.me/oauth2/v2.1/verify"

    # --- 辨識服務（同機內部呼叫，見 contracts/recognition-service.md）---
    recognition_service_url: str = "http://localhost:8900"
    # ⚠️ OQ-4：暫定值，需以 recognition_jobs.duration_ms 實測後校準
    recognition_timeout_seconds: float = 30.0

    # --- 照片 ---
    photo_storage_root: Path = Path("./var/photos")
    photo_max_bytes: int = 10 * 1024 * 1024
    photo_allowed_content_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )

    # --- 其他 ---
    app_timezone: str = "Asia/Taipei"
    #: LINE Login 的 Callback URL 已不接受 http，本機開發常改跑 HTTPS
    #: 或透過通道，因此預設同時涵蓋這些來源。走 ngrok／cloudflared 時
    #: 需自行把該網域加進 CORS_ORIGINS 環境變數。
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "https://localhost:3000",
            "http://127.0.0.1:3000",
            "https://127.0.0.1:3000",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
