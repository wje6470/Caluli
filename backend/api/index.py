"""Vercel Python Runtime 的進入點。

只做一件事：把既有的 FastAPI app 暴露給 Vercel。路由、中介層與路徑前綴
處理都在 app/main.py，本機以 uvicorn 執行時完全不經過這個檔案。

⚠️ sys.path 處理是必要的
   本檔位於 api/ 之下，而 `app` 套件在其上一層。Python 預設只把「腳本
   所在目錄」放進 sys.path，因此 `import app.main` 會失敗；失敗的結果是
   函式壓根沒被建立，對外表現為所有路徑 404（而非 500），很容易誤判成
   路由設定錯誤。

註：Vercel 的 rewrite 會把路徑改寫成 /api/index/<原始路徑>。這個前綴由
    app/main.py 的 root_path 處理，不在此處攔截——實測發現 Vercel 會直接
    取用模組中的 FastAPI 實例，在本檔包一層 ASGI 中介層並不會被呼叫。
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.main import app  # noqa: E402 — 須在 sys.path 調整後匯入

__all__ = ["app"]
