"""可切換模式的假辨識服務。

模擬真實的「台灣小吃辨識 API」契約，讓錯誤處理路徑在不消耗真實服務
金鑰額度、不依賴外部網路的情況下完整驗證。契約定義見
specs/001-diet-log-mvp/contracts/recognition-service.md（2026-08-04 修訂）。

用法：
    uv run uvicorn stub:app --port 8900
    POST /api/detect?mode=empty
"""

import asyncio
import os

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="Recognition Service Stub")

DEFAULT_MODE = os.getenv("STUB_DEFAULT_MODE", "normal")

NORMAL_ITEMS = [
    {
        "name": "滷肉飯",
        "estimated_weight_g": 250,
        "calories": 535.0,
        "protein_g": 20.0,
        "carbs_g": 60.0,
        "fat_g": 22.5,
        "confidence": 0.93,
        "class_name": "braised_pork_over_rice",
        "bbox": {"x1": 120, "y1": 80, "x2": 340, "y2": 260},
    },
    {
        "name": "炒青菜",
        "estimated_weight_g": 120,
        "calories": 78.0,
        "protein_g": 3.0,
        "carbs_g": 6.0,
        "fat_g": 4.8,
        "confidence": 0.81,
        "class_name": "stir_fried_greens",
        "bbox": {"x1": 560, "y1": 140, "x2": 820, "y2": 380},
    },
]

ZERO_WEIGHT_ITEMS = [
    {
        "name": "無法估算份量的品項",
        "estimated_weight_g": 0,
        "calories": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "confidence": 0.55,
        "class_name": "unclassified",
        "bbox": None,
    }
]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "default_mode": DEFAULT_MODE}


@app.post("/api/detect")
async def detect(
    file: UploadFile = File(...),  # noqa: ARG001 — 介面需要，stub 不讀內容
    mode: str = Query(default=None),
):
    effective = mode or DEFAULT_MODE

    if effective == "empty":
        # 真實服務不提供 message 欄位；後端 adapter 須自行合成前端顯示文案。
        return {"items": []}

    if effective == "timeout":
        # 超過後端的 RECOGNITION_TIMEOUT_SECONDS（預設 30s）。
        await asyncio.sleep(60)
        return {"items": NORMAL_ITEMS}

    if effective == "error":
        return JSONResponse(status_code=500, content={"detail": "internal model failure"})

    if effective == "unauthorized":
        # 模擬缺少或錯誤的 X-API-Key。
        return JSONResponse(status_code=401, content={"detail": "invalid or missing X-API-Key"})

    if effective == "garbage":
        return PlainTextResponse("<html>502 Bad Gateway</html>", status_code=200)

    if effective == "zero_weight":
        # estimated_weight_g = 0：後端須降級為 nutrition_available=false，不得整次失敗。
        return {"items": ZERO_WEIGHT_ITEMS}

    return {"items": NORMAL_ITEMS}
