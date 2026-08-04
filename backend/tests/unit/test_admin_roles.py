"""管理員名單核對（tasks.md T010，spec FR-005～FR-009）。

★ 本輪的關鍵路徑是**降級**，不是升級
=====================================
名單是單一真實來源，故核對必須雙向：在名單內 → admin，不在名單內 → user。
只升不降的實作會讓「從名單移除」完全失效（FR-007），而那種 bug 在手動
測試時幾乎不會被發現——管理員自己測不會去測「我被移除後還能不能進」。
故 test_admin_role_revoked_when_removed_from_allowlist() 是本檔最重要的一項。

本檔刻意**不依賴資料庫**：resolve_role() 是純函式，因此 Docker 不可用時
這些測試仍會執行（見 conftest.py 的說明）。
"""

import pytest

from app.core.config import get_settings
from app.db.models import ROLE_ADMIN, ROLE_USER
from app.services.admin_roles import resolve_role

ADMIN_SUB = "U0123456789abcdef0123456789abcdef"
OTHER_SUB = "Ufedcba9876543210fedcba9876543210"


@pytest.fixture
def allowlist(monkeypatch):
    """設定管理員名單。

    get_settings() 帶 lru_cache，直接改環境變數不會生效——必須清快取，
    且測試結束後要再清一次，否則污染同一 session 的其他測試。
    """

    def install(raw: str):
        monkeypatch.setenv("ADMIN_LINE_USER_IDS", raw)
        get_settings.cache_clear()

    yield install
    monkeypatch.undo()
    get_settings.cache_clear()


def test_line_id_in_allowlist_becomes_admin(allowlist):
    allowlist(ADMIN_SUB)
    assert resolve_role(ADMIN_SUB) == ROLE_ADMIN


def test_line_id_not_in_allowlist_stays_normal_user(allowlist):
    allowlist(ADMIN_SUB)
    assert resolve_role(OTHER_SUB) == ROLE_USER


def test_admin_role_revoked_when_removed_from_allowlist(allowlist):
    """★ FR-007：自名單移除後，下次登入必須降回一般使用者。

    這是「雙向同步」與「只升不降」兩種實作的分水嶺。
    """
    allowlist(ADMIN_SUB)
    assert resolve_role(ADMIN_SUB) == ROLE_ADMIN

    # 營運方把該帳號移出名單並重啟後端。
    allowlist("")
    assert resolve_role(ADMIN_SUB) == ROLE_USER, "移出名單後必須降為一般使用者，不得停留在 admin"


def test_empty_allowlist_makes_everyone_a_normal_user(allowlist):
    """FR-008：名單為空時系統正常運作，而非退回「無人設定即全體開放」。"""
    allowlist("")
    assert resolve_role(ADMIN_SUB) == ROLE_USER
    assert resolve_role(OTHER_SUB) == ROLE_USER


def test_unset_allowlist_does_not_raise(allowlist, monkeypatch):
    """FR-008：完全未設定此環境變數時不得啟動失敗。"""
    monkeypatch.delenv("ADMIN_LINE_USER_IDS", raising=False)
    get_settings.cache_clear()
    assert resolve_role(ADMIN_SUB) == ROLE_USER


@pytest.mark.parametrize(
    "raw",
    [
        f"{ADMIN_SUB},{OTHER_SUB}",
        f"{ADMIN_SUB}, {OTHER_SUB}",
        f"  {ADMIN_SUB}  ,  {OTHER_SUB}  ",
        f"{ADMIN_SUB},\n{OTHER_SUB}",
        f",{ADMIN_SUB},,{OTHER_SUB},",
    ],
    ids=["plain", "space-after-comma", "padded", "newline", "empty-segments"],
)
def test_allowlist_parsing_tolerates_whitespace_and_empty_segments(allowlist, raw):
    """設定值常從多行貼上，容錯不足會造成「明明加了卻沒生效」的難解狀況。"""
    allowlist(raw)
    assert resolve_role(ADMIN_SUB) == ROLE_ADMIN
    assert resolve_role(OTHER_SUB) == ROLE_ADMIN


def test_whitespace_only_allowlist_grants_nobody(allowlist):
    """全是分隔符與空白時不得解析出一個空字串成員而讓空 sub 通過。"""
    allowlist(" , , ")
    assert resolve_role(ADMIN_SUB) == ROLE_USER
    assert resolve_role("") == ROLE_USER


def test_matching_is_exact_not_prefix(allowlist):
    """避免以 startswith／子字串比對造成越權。"""
    allowlist(ADMIN_SUB)
    assert resolve_role(ADMIN_SUB[:-1]) == ROLE_USER
    assert resolve_role(ADMIN_SUB + "x") == ROLE_USER
