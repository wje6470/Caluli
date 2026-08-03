"""可切換模式的假辨識服務。

真辨識服務就緒前替代之，讓錯誤處理路徑能完整驗證——那是本輪需求密度
最高、最容易漏測的區塊。模式定義見
specs/001-diet-log-mvp/contracts/recognition-service.md

用法：
    uv run uvicorn stub:app --port 8900
    POST /predict?mode=empty
"""

import asyncio
import os

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="Recognition Service Stub")

DEFAULT_MODE = os.getenv("STUB_DEFAULT_MODE", "normal")

NORMAL_ITEMS = [
    {
        "label": "braised_pork_rice",
        "confidence": 0.93,
        "bbox": {"x": 120, "y": 88, "width": 420, "height": 380},
        "candidates": [
            {"label": "braised_pork_rice", "confidence": 0.93},
            {"label": "braised_pork_belly_rice", "confidence": 0.05},
            {"label": "minced_pork_rice", "confidence": 0.02},
        ],
    },
    {
        "label": "stir_fried_greens",
        "confidence": 0.81,
        "bbox": {"x": 560, "y": 140, "width": 260, "height": 240},
        "candidates": [
            {"label": "stir_fried_greens", "confidence": 0.81},
            {"label": "dumplings", "confidence": 0.11},
        ],
    },
]

UNKNOWN_LABEL_ITEMS = [
    {
        "label": "label_not_in_reference_table",
        "confidence": 0.77,
        "bbox": None,
        "candidates": [{"label": "label_not_in_reference_table", "confidence": 0.77}],
    }
]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "default_mode": DEFAULT_MODE}


@app.post("/predict")
async def predict(
    photo: UploadFile = File(...),  # noqa: ARG001 — 介面需要，stub 不讀內容
    mode: str = Query(default=None),
):
    effective = mode or DEFAULT_MODE

    if effective == "empty":
        # 已確認的錯誤／空結果格式。後端須視為**成功**（HTTP 200）。
        return {"items": [], "message": "沒有偵測到食物，請換一張再試試"}

    if effective == "timeout":
        # 超過後端的 RECOGNITION_TIMEOUT_SECONDS（預設 30s）。
        await asyncio.sleep(60)
        return {"items": NORMAL_ITEMS, "message": None}

    if effective == "error":
        return JSONResponse(status_code=500, content={"detail": "internal model failure"})

    if effective == "garbage":
        return PlainTextResponse("<html>502 Bad Gateway</html>", status_code=200)

    if effective == "unknown_label":
        return {"items": UNKNOWN_LABEL_ITEMS, "message": None}

    return {"items": NORMAL_ITEMS, "message": None}
