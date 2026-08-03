"""Vercel Python Runtime 的進入點。

Vercel 會尋找 `api/` 目錄下的檔案作為 Serverless Function。此處只是把
既有的 FastAPI app 暴露為 ASGI 應用，不含任何額外邏輯——所有路由與
中介層仍定義在 app/main.py，本機以 uvicorn 執行時完全不經過這個檔案。

搭配 vercel.json 的 rewrites，所有路徑都導到這裡由 FastAPI 自行路由。
"""

from app.main import app

# Vercel 的 Python runtime 會偵測名為 `app` 的 ASGI 可呼叫物件。
__all__ = ["app"]
