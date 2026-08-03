"""Vercel Python Runtime 的進入點。

把既有的 FastAPI app 暴露為 ASGI 應用，不含任何業務邏輯——路由與中介層
仍定義在 app/main.py，本機以 uvicorn 執行時完全不經過這個檔案。

處理兩件 Vercel 特有的事：

1. sys.path
   本檔位於 api/ 之下，而 `app` 套件在其上一層。Python 預設只把「腳本
   所在目錄」放進 sys.path，因此 `import app.main` 會失敗；失敗的結果是
   函式壓根沒被建立，對外表現為所有路徑 404（而非 500）。

2. 路徑還原
   vercel.json 以 `"destination": "/api/index/$1"` 把原始路徑接在後面，
   FastAPI 收到的會是 `/api/index/healthz` 這種形式。此處在交給 FastAPI
   之前把 `/api/index` 前綴剝掉，讓路由比對看到的是 `/healthz`。

   若不做這件事，FastAPI 會對每個請求都回 `{"detail":"Not Found"}`——
   看起來像路由沒註冊，實際上是路徑被 rewrite 蓋掉了。
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.main import app as fastapi_app  # noqa: E402 — 須在 sys.path 調整後匯入

#: 與 vercel.json 的 rewrite destination 相對應。
VERCEL_PREFIX = "/api/index"


async def app(scope, receive, send):
    """ASGI 包裝層：還原被 Vercel rewrite 覆蓋的請求路徑。"""
    if scope["type"] in ("http", "websocket"):
        path: str = scope.get("path", "")
        if path == VERCEL_PREFIX or path.startswith(VERCEL_PREFIX + "/"):
            restored = path[len(VERCEL_PREFIX) :] or "/"
            scope = dict(scope)
            scope["path"] = restored
            scope["raw_path"] = restored.encode("utf-8")

    await fastapi_app(scope, receive, send)


__all__ = ["app"]
