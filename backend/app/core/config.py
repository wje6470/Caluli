"""應用設定。變數清單與 specs/001-diet-log-mvp/quickstart.md 一致。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- 資料庫 ---
    #
    # 本機：postgresql+psycopg://caluli:caluli@127.0.0.1:55432/caluli_dev
    #
    # Supabase：使用 Dashboard 的 Connection string，並加上 +psycopg 與 sslmode。
    #   postgresql+psycopg://postgres.<ref>:<pw>@<host>.pooler.supabase.com:5432/postgres?sslmode=require
    #
    #   ⚠️ 選用 **Session pooler（5432）** 而非 Transaction pooler（6543）：
    #      後端是長時間運行的 uvicorn 並自帶連線池，session 模式行為與直連一致；
    #      transaction 模式不支援 prepared statements，psycopg 需額外停用才不會出錯。
    #   ⚠️ 直連端點（db.<ref>.supabase.co）在新專案僅提供 IPv6，
    #      無 IPv4 add-on 時連不上，故一律走 pooler 主機。
    database_url: str = "postgresql+psycopg://caluli:caluli@127.0.0.1:55432/caluli_dev"

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

    # --- 辨識服務（第三方代管的「台灣小吃辨識 API」，見 contracts/recognition-service.md）---
    #
    # 本機／CI 預設指向 tools/recognition-stub；正式環境覆寫為：
    #   https://taiwanese-food-api-528488788338.asia-east1.run.app
    recognition_service_url: str = "http://localhost:8900"
    #: X-API-Key 認證用金鑰。呼叫 stub 時可留空（stub 不驗證此值）；
    #: 正式環境呼叫真實服務時必填，缺少會導致對外一律回 401（research.md R-16）。
    recognition_api_key: str = ""
    # ⚠️ OQ-4：暫定值，需以 recognition_jobs.duration_ms 實測後校準
    # （正式環境為外部服務，需涵蓋公網延遲，見 research.md R-07 的 2026-08-04 更新）
    recognition_timeout_seconds: float = 30.0

    # --- Supabase Storage（正式環境的照片儲存）---
    #
    # Vercel serverless 的檔案系統唯讀且短暫，無法保存使用者照片，
    # 故正式環境改存 Supabase Storage。兩者皆設定時優先使用 Supabase。
    #
    # ⚠️ bucket 必須設為 **private**。照片只透過後端的
    #    /meal-records/{id}/photo 端點提供（該端點驗證擁有者）；
    #    設為 public 等同繞過 FR-044 的資料隔離。
    supabase_url: str = ""
    supabase_service_key: str = ""
    photo_bucket: str = "meal-photos"
    storage_timeout_seconds: float = 20.0

    # --- 照片 ---
    #: 僅在未設定 Supabase 時使用（本機開發）。
    photo_storage_root: Path = Path("./var/photos")
    photo_max_bytes: int = 10 * 1024 * 1024
    photo_allowed_content_types: tuple[str, ...] = (
        "image/jpeg",
        "image/png",
        "image/webp",
    )

    # --- 推薦餐廳（第二輪）---
    #
    # 兩個值集中於此而非散落在服務層：半徑是暫定值（OQ-7），實地測試後
    # 很可能調整，散落多處會漏改。
    #
    #: 「附近」的距離上限（公里）。超過此距離的店家不出現在距離排序清單中，
    #: 即使範圍內不足 nearby_limit 家也不以範圍外的店家補足（spec FR-020）。
    nearby_radius_km: float = 5.0
    #: 距離排序清單的回傳筆數上限（spec FR-014）。
    nearby_limit: int = 10

    # --- 管理員名單（第三輪，憲章原則 IV）---
    #
    # 管理員身分**只能**由此設定指派，系統中不存在任何可寫入 users.role
    # 的 API。登入時（services/admin_roles.py）以此名單核對並**雙向同步**：
    # 在名單內 → admin，不在名單內 → user。
    #
    # ⚠️ 因為是雙向同步，**直接改資料庫授予 admin 無效**（下次登入被覆寫）。
    #    資料庫直改僅能作為緊急撤銷手段，且撤銷後必須同步移出本名單，
    #    否則下次登入即復原。
    #
    # ⚠️ 格式為**半形逗號分隔的字串**，不是 JSON 陣列——pydantic-settings
    #    對 list[str] 欄位要求環境變數為 JSON，而引號在 .env、docker-compose
    #    與 Vercel 環境變數面板中都容易被吃掉或轉義錯誤。
    #
    # 留空 = 無人是管理員（後台無人可進入），而非全體開放。
    admin_line_user_ids: str = ""

    # --- 其他 ---
    #: 部署於 Vercel 等 serverless 平台時設為 true。
    #: 影響資料庫連線策略（見 db/session.py）——serverless 下必須關閉
    #: SQLAlchemy 連線池並停用 prepared statements。
    serverless: bool = False

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

    @property
    def admin_line_user_id_set(self) -> frozenset[str]:
        """管理員 LINE user ID 集合。

        容忍逗號後的空白與換行——設定值常從多行貼上。回傳 frozenset
        使核對為 O(1) 且不可變，杜絕任何位置意外修改名單。
        """
        return frozenset(
            piece.strip() for piece in self.admin_line_user_ids.split(",") if piece.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
