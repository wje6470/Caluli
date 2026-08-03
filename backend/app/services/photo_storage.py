"""照片儲存（research.md R-10）。

存取一律經後端端點並驗證擁有者，不開放公開網址——路徑可猜測即可讀取
不是存取控制（FR-044）。

兩種實作，由設定自動選擇：

  FileSystemPhotoStorage  本機開發。寫入 PHOTO_STORAGE_ROOT。
  SupabasePhotoStorage    正式環境。Vercel serverless 的檔案系統唯讀且
                          短暫，無法保存照片，故改存 Supabase Storage。

R-10 當初就把儲存抽象成 Protocol，正是為了這種替換不必動到業務層。
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import get_settings


class PhotoStorage(Protocol):
    def save(self, user_id: uuid.UUID, content: bytes) -> str: ...
    def read(self, relative_path: str) -> bytes: ...
    def delete(self, relative_path: str) -> None: ...
    def exists(self, relative_path: str) -> bool: ...


def _object_path(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    return f"{user_id}/{now:%Y}/{now:%m}/{uuid.uuid4()}.jpg"


class FileSystemPhotoStorage:
    """本機開發用。"""

    def __init__(self, root: Path | None = None):
        self._root = Path(root or get_settings().photo_storage_root)

    def _absolute(self, relative_path: str) -> Path:
        target = (self._root / relative_path).resolve()
        root = self._root.resolve()
        # 防路徑穿越：拒絕任何解析後跳出 root 的路徑。
        if not target.is_relative_to(root):
            raise ValueError("照片路徑超出允許範圍")
        return target

    def save(self, user_id: uuid.UUID, content: bytes) -> str:
        relative = _object_path(user_id)
        absolute = self._absolute(relative)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(content)
        return relative

    def read(self, relative_path: str) -> bytes:
        return self._absolute(relative_path).read_bytes()

    def delete(self, relative_path: str) -> None:
        self._absolute(relative_path).unlink(missing_ok=True)

    def exists(self, relative_path: str) -> bool:
        return self._absolute(relative_path).is_file()


class SupabasePhotoStorage:
    """Supabase Storage 實作。

    使用 service role key 直接呼叫 Storage REST API。bucket 必須設為
    **private**——照片只透過後端的 /meal-records/{id}/photo 端點提供，
    該端點會驗證擁有者。若 bucket 設為 public，任何人拿到路徑即可讀取，
    等同繞過 FR-044 的資料隔離。
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_key:
            raise ValueError("未設定 SUPABASE_URL 或 SUPABASE_SERVICE_KEY")

        self._base = f"{settings.supabase_url.rstrip('/')}/storage/v1/object"
        self._bucket = settings.photo_bucket
        self._headers = {
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "apikey": settings.supabase_service_key,
        }
        self._timeout = settings.storage_timeout_seconds

    def _url(self, relative_path: str) -> str:
        return f"{self._base}/{self._bucket}/{relative_path}"

    def save(self, user_id: uuid.UUID, content: bytes) -> str:
        relative = _object_path(user_id)
        response = httpx.post(
            self._url(relative),
            content=content,
            headers={**self._headers, "Content-Type": "image/jpeg"},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return relative

    def read(self, relative_path: str) -> bytes:
        response = httpx.get(
            self._url(relative_path), headers=self._headers, timeout=self._timeout
        )
        response.raise_for_status()
        return response.content

    def delete(self, relative_path: str) -> None:
        response = httpx.delete(
            self._url(relative_path), headers=self._headers, timeout=self._timeout
        )
        # 已不存在視為刪除成功——刪除應為冪等操作。
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()

    def exists(self, relative_path: str) -> bool:
        try:
            response = httpx.head(
                self._url(relative_path), headers=self._headers, timeout=self._timeout
            )
        except httpx.HTTPError:
            return False
        return response.status_code == 200


def get_photo_storage() -> PhotoStorage:
    """依設定選擇實作。設定了 Supabase 就用它，否則回退到本機檔案系統。"""
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_key:
        return SupabasePhotoStorage()
    return FileSystemPhotoStorage()
