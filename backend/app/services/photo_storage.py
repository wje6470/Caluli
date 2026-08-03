"""照片儲存（research.md R-10）。

同機檔案系統，資料庫只存相對路徑。存取一律經後端端點並驗證擁有者，
不開放靜態目錄直接對外——路徑可猜測即可讀取不是存取控制（FR-044）。

介面化以利日後替換為物件儲存而不需改動業務層。
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class PhotoStorage(Protocol):
    def save(self, user_id: uuid.UUID, content: bytes) -> str: ...
    def read(self, relative_path: str) -> bytes: ...
    def delete(self, relative_path: str) -> None: ...
    def exists(self, relative_path: str) -> bool: ...


class FileSystemPhotoStorage:
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
        now = datetime.now(UTC)
        relative = f"{user_id}/{now:%Y}/{now:%m}/{uuid.uuid4()}.jpg"
        absolute = self._absolute(relative)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(content)
        return relative

    def read(self, relative_path: str) -> bytes:
        return self._absolute(relative_path).read_bytes()

    def delete(self, relative_path: str) -> None:
        absolute = self._absolute(relative_path)
        absolute.unlink(missing_ok=True)

    def exists(self, relative_path: str) -> bool:
        return self._absolute(relative_path).is_file()


def get_photo_storage() -> PhotoStorage:
    return FileSystemPhotoStorage()
