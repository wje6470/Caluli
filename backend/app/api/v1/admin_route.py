"""管理端專用的 APIRoute：把驗證錯誤轉成統一錯誤信封。

★ 為什麼不用全域的 exception handler
====================================
第一輪沒有註冊 RequestValidationError handler，驗證失敗時回的是 FastAPI
預設的 `{"detail": [...]}`，而非本專案的錯誤信封 `{"error": {...}}`。
前端的 parseError() 找不到 `error` 欄位，會退回通用訊息「系統發生問題，
請稍後再試。」——管理員在表單填錯座標時看到這句話，等於沒有提示。

修正它需要一個 RequestValidationError handler，但 handler 是**應用層全域**
的，掛上去會連帶改變第一輪既有端點的錯誤回應格式，違反 spec FR-043
「不得修改既有 API 的行為」。

改用自訂 route class，範圍精確限縮在掛載它的 router：
    APIRouter(..., route_class=AdminAPIRoute)

第一輪的端點完全不受影響。

★ 訊息品質
==========
FR-047 要求失敗時說明原因與可採取的下一步。pydantic 的原始訊息是英文且
帶技術術語（"Input should be less than or equal to 90"），故此處轉譯成
可直接呈現給管理員的中文。
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

from app.core.errors import AppError

#: 欄位代碼 → 管理員看得懂的名稱。
_FIELD_LABELS = {
    "name": "名稱",
    "address": "地址",
    "latitude": "緯度",
    "longitude": "經度",
    "calories": "熱量",
    "protein_g": "蛋白質",
    "carbs_g": "碳水化合物",
    "fat_g": "脂肪",
}

#: pydantic 錯誤類型 → 中文說明。未列出者退回通用說明。
_REASONS = {
    "missing": "為必填欄位。",
    "string_too_short": "不得為空白。",
    "string_too_long": "長度超過上限。",
    "greater_than_equal": "數值超出允許範圍。",
    "less_than_equal": "數值超出允許範圍。",
    "decimal_parsing": "必須是數字。",
    "float_parsing": "必須是數字。",
    "int_parsing": "必須是數字。",
    "decimal_type": "必須是數字。",
    "float_type": "必須是數字。",
    "string_type": "必須是文字。",
}


def _readable(exc: RequestValidationError) -> str:
    """取第一項錯誤轉成可呈現的中文。

    只取第一項而非全部：後台表單欄位少，逐項列出反而讓訊息冗長；
    修正第一項後若仍有問題，下一次送出會提示下一項。
    """
    errors = exc.errors()
    if not errors:
        return "輸入的資料不正確，請檢查後再試。"

    first = errors[0]
    error_type = first.get("type", "")

    # 我們自己在 model_validator 中 raise 的 ValueError，訊息本來就是
    # 可直接呈現的中文，原樣使用（pydantic 會加上 "Value error, " 前綴）。
    if error_type == "value_error":
        message = str(first.get("msg", "")).removeprefix("Value error, ").strip()
        if message:
            return message

    # loc 形如 ("body", "latitude")；取最後一個非 "body" 的片段。
    location = [str(part) for part in first.get("loc", ()) if part != "body"]
    field = location[-1] if location else ""
    label = _FIELD_LABELS.get(field, field)

    reason = _REASONS.get(error_type, "格式不正確。")
    return f"{label}{reason}" if label else f"輸入的資料{reason}"


class AdminAPIRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError as exc:
                # 轉成 AppError 後由既有的 app_error_handler 統一輸出信封，
                # 錯誤格式與其他管理端回應一致。
                raise AppError("VALIDATION_ERROR", message=_readable(exc)) from exc

        return handler
