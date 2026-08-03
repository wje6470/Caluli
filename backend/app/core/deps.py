"""FastAPI 依賴注入。

憲章原則 IV — 角色與權限隔離
================================
兩層依賴刻意分開：

  get_current_user()  — 本輪所有端點使用
  require_admin()     — 本輪**不掛載於任何端點**，僅建立並附單元測試

先建立 require_admin() 的理由：憲章要求「須建立僅管理員可通過的權限
檢查層」，且要求本輪設計不得妨礙後續加入。先放骨架的成本接近零，卻讓
憲章明列的必測情境「一般使用者存取管理端 API 被拒絕」在本輪就能成立。

所有資料查詢一律以 user_id 收斂，不存在「查全部再過濾」的路徑。
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.models import ROLE_ADMIN, User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise AppError("UNAUTHORIZED")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AppError("UNAUTHORIZED")

    user = db.get(User, user_id)
    if user is None:
        raise AppError("UNAUTHORIZED")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    """管理員專用權限檢查層。

    本輪沒有任何端點掛載此依賴（管理員後台屬第二輪）。它存在的意義是：
    第二輪加入後台端點時，只需掛上此依賴即可，不需重新設計授權層。
    """
    if user.role != ROLE_ADMIN:
        raise AppError("FORBIDDEN")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
