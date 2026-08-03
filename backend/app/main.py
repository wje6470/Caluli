"""FastAPI 應用進入點。

憲章原則 III：單一後端服務所有客戶端（LIFF、一般網頁，以及後續輪次的
iOS／Android）。此處**不存在**任何依客戶端分岔的路由或中介層。
"""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import analytics, auth, foods, meal_records, profile, recognitions
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(
    title="Caluli 飲食紀錄 API（第一輪 MVP）",
    version="0.1.0",
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
def healthz() -> dict[str, str]:
    return {"status": "ok"}
