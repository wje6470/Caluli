"""統一錯誤信封與 code → HTTP 對照（research.md R-08）。

前端依 `retryable` 決定是否顯示「重試」，不必自行維護 code 對照表。

⚠️ 注意「未偵測到食物」**不在此列**——那是成功的辨識結果（HTTP 200、
items: []），不是錯誤。把它歸為錯誤會讓前端落入通用錯誤處理而渲染出
空的結果清單，正是 FR-027 明文禁止的行為。
"""

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class ErrorSpec:
    status_code: int
    message: str
    retryable: bool


ERROR_CATALOG: dict[str, ErrorSpec] = {
    "UNAUTHORIZED": ErrorSpec(401, "請重新登入。", False),
    "FORBIDDEN": ErrorSpec(403, "沒有執行此操作的權限。", False),
    "NOT_FOUND": ErrorSpec(404, "找不到指定的資料。", False),
    "VALIDATION_ERROR": ErrorSpec(422, "輸入的資料不正確，請檢查後再試。", False),
    "PAYLOAD_TOO_LARGE": ErrorSpec(413, "照片檔案太大，請選擇 10MB 以內的照片。", False),
    "UNSUPPORTED_MEDIA_TYPE": ErrorSpec(
        415, "不支援這種檔案格式，請選擇 JPEG、PNG 或 WebP 照片。", False
    ),
    # --- 辨識服務相關（皆可重試，且重試不需重新上傳照片）---
    "RECOGNITION_TIMEOUT": ErrorSpec(504, "辨識花費的時間比預期長，請再試一次。", True),
    "RECOGNITION_UNAVAILABLE": ErrorSpec(503, "辨識服務目前忙碌中，請稍後再試。", True),
    # 技術細節（回應無法解析）不外露給使用者。
    "RECOGNITION_BAD_RESPONSE": ErrorSpec(502, "辨識結果讀取失敗，請再試一次。", True),
    "INTERNAL_ERROR": ErrorSpec(500, "系統發生問題，請稍後再試。", False),
}


class AppError(Exception):
    """帶錯誤代碼的應用例外。訊息一律可直接呈現給使用者。"""

    def __init__(self, code: str, *, message: str | None = None, detail: str | None = None):
        spec = ERROR_CATALOG.get(code, ERROR_CATALOG["INTERNAL_ERROR"])
        self.code = code if code in ERROR_CATALOG else "INTERNAL_ERROR"
        self.spec = spec
        self.message = message or spec.message
        #: 僅供伺服器端記錄，不放進回應。
        self.detail = detail
        super().__init__(self.message)

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.spec.status_code,
            content={
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "retryable": self.spec.retryable,
                }
            },
        )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return exc.to_response()


def error_payload(code: str, message: str | None = None) -> dict[str, dict[str, object]]:
    spec = ERROR_CATALOG[code]
    return {
        "error": {
            "code": code,
            "message": message or spec.message,
            "retryable": spec.retryable,
        }
    }
