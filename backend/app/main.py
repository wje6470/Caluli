"""FastAPI 應用進入點。

憲章原則 III：單一後端服務所有客戶端（LIFF、一般網頁，以及後續輪次的
iOS／Android）。此處**不存在**任何依客戶端分岔的路由或中介層。
"""

import logging
import os

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import analytics, auth, foods, meal_records, profile, recognitions
from app.core.config import get_settings
from app.core.deps import DbSession
from app.core.errors import AppError, app_error_handler

logging.basicConfig(level=logging.INFO)

settings = get_settings()

# Vercel 的 rewrite 會把請求路徑改寫成 /api/index/<原始路徑>，FastAPI 收到的
# 因此帶有 /api/index 前綴。root_path 正是為這種「位於路徑前綴的反向代理之後」
# 的情境而設計——Starlette 在路由比對前會先把它從 path 剝除。
#
# 用 VERCEL 這個環境變數判斷（Vercel 於所有部署自動注入），本機為空字串，
# 兩種環境共用同一份程式碼。
#
# 曾嘗試在 api/index.py 包一層 ASGI 中介層改寫 scope["path"]，但 Vercel 的
# Python runtime 會直接取用模組中的 FastAPI 實例，不經過該包裝函式。
_ROOT_PATH = "/api/index" if os.getenv("VERCEL") else ""

app = FastAPI(
    title="Caluli 飲食紀錄 API（第一輪 MVP）",
    version="0.1.0",
    root_path=_ROOT_PATH,
    description=(
        "LIFF 與一般網頁共用的單一後端 API。\n\n"
        "免責：本 API 提供的營養數值為估算參考，不構成醫療級營養診斷或"
        "治療建議（憲章原則 VII）。"
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # 使用 Bearer token，不依賴 Cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)

v1 = APIRouter(prefix="/api/v1")
v1.include_router(auth.router)
v1.include_router(profile.router)
v1.include_router(recognitions.router)
v1.include_router(meal_records.router)
v1.include_router(analytics.router)
v1.include_router(foods.router)
app.include_router(v1)


@app.get("/healthz", tags=["ops"])
def healthz(db: DbSession) -> dict[str, str]:
    """存活檢查，並回報資料庫可達性。

    刻意**不因資料庫不可用而回非 200**——這支端點同時作為部署診斷用，
    需要能區分「應用沒起來」（連不上／404）與「應用起來了但資料庫不通」。
    兩者若都表現為失敗，排查時無從分辨。
    """
    try:
        db.execute(text("select 1"))
        database = "ok"
    except Exception as exc:  # noqa: BLE001 — 診斷用途，任何連線問題都要能回報
        logging.warning("健康檢查的資料庫查詢失敗：%s", exc)
        database = f"unreachable: {type(exc).__name__}"

    return {"status": "ok", "database": database}


@app.api_route(
    "/{unmatched_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
def not_found(request: Request, unmatched_path: str) -> JSONResponse:
    """未匹配任何路由時，回報**實際收到的路徑**。

    這條必須註冊在所有 router 之後，因此只會接到真正沒對上的請求。

    存在的理由：反向代理或平台層的 rewrite（例如 Vercel）可能改寫請求
    路徑，此時 FastAPI 對每個請求都回 404，外觀與「路由沒註冊」完全相同，
    從外部無從分辨。把收到的路徑回報出來，可讓這類問題一眼看穿而不必猜。
    """
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Not Found",
            "received_path": request.url.path,
            "root_path": request.scope.get("root_path", ""),
        },
    )
