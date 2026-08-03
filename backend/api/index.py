"""Vercel Python Runtime 的進入點。

Vercel 會把 `api/` 目錄下的檔案建成 Serverless Function。此處只是把既有的
FastAPI app 暴露為 ASGI 應用，不含任何業務邏輯——路由與中介層仍定義在
app/main.py，本機以 uvicorn 執行時完全不經過這個檔案。

⚠️ sys.path 處理是必要的：這個檔案位於 api/ 之下，而要匯入的 `app` 套件
   在其上一層（專案根目錄）。Python 預設把「腳本所在目錄」放進 sys.path，
   也就是 api/，因此 `import app.main` 會找不到模組而讓建置失敗——
   失敗的結果是函式壓根沒被建立，對外表現為所有路徑 404（而非 500），
   很容易誤判成路由設定錯誤。
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.main import app  # noqa: E402 — 必須在 sys.path 調整之後才能匯入

# Vercel 的 Python runtime 會偵測名為 `app` 的 ASGI 可呼叫物件。
__all__ = ["app"]
