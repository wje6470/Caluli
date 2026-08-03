"""憲章原則 IV 必測情境：一般使用者存取管理端 API 被拒絕。

本輪沒有任何端點掛載 require_admin()，因此直接測試該依賴本身——
憲章要求此情境在本輪就必須有測試，不能等到有端點才補。
"""

import uuid

import pytest

from app.core.deps import require_admin
from app.core.errors import AppError
from app.db.models import ROLE_ADMIN, ROLE_USER, User


def make_user(role: str) -> User:
    user = User()
    user.id = uuid.uuid4()
    user.line_user_id = f"U{uuid.uuid4().hex}"
    user.role = role
    return user


def test_require_admin_rejects_normal_user():
    """一般使用者的合法登入狀態不得通過管理員權限檢查層。"""
    user = make_user(ROLE_USER)

    with pytest.raises(AppError) as exc_info:
        require_admin(user)

    assert exc_info.value.code == "FORBIDDEN"
    assert exc_info.value.spec.status_code == 403
    assert exc_info.value.spec.retryable is False


def test_require_admin_allows_admin_user():
    user = make_user(ROLE_ADMIN)
    assert require_admin(user) is user


def test_user_role_defaults_to_normal_user():
    """本輪所有使用者皆為一般使用者；role 不得預設為 admin。"""
    user = User(line_user_id="Utest")
    assert user.role is None or user.role == ROLE_USER
    assert make_user(ROLE_USER).is_admin is False
