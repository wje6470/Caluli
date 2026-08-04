"""登入流程的角色同步（tasks.md T013，spec FR-006～FR-009）。

test_admin_roles.py 測的是 resolve_role() 這個純函式；本檔測的是**它有沒有
真的被接上登入流程**。兩者缺一不可——名單邏輯再正確，沒接進 upsert_user()
也等於沒有。

★ 為什麼掛在 upsert_user()
==========================
它是 LIFF 與一般網頁唯一的匯流點（憲章原則 I）。test_both_entries_assign_
the_same_role() 就是在驗證這件事：兩個入口走完全不同的前半段，卻必須得到
相同的角色判定。若哪天有人為某個入口寫了特例，該測試會失敗。
"""

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ROLE_ADMIN, ROLE_USER, User
from app.db.session import get_db
from app.main import app

ADMIN_SUB = "U0123456789abcdef0123456789abcdef"
NORMAL_SUB = "Ufedcba9876543210fedcba9876543210"


@pytest.fixture
def client(db_session: Session):
    """回傳 client 工廠——多次登入的測試需要各自獨立的 client 實例
    （httpx 的 client 一旦離開 async with 就無法重開）。"""
    app.dependency_overrides[get_db] = lambda: db_session
    transport = httpx.ASGITransport(app=app)

    def make() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    yield make
    app.dependency_overrides.clear()


@pytest.fixture
def allowlist(monkeypatch):
    """設定管理員名單。get_settings() 有 lru_cache，改環境變數後必須清快取。"""

    def install(raw: str):
        monkeypatch.setenv("ADMIN_LINE_USER_IDS", raw)
        get_settings.cache_clear()

    yield install
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def line_api(monkeypatch):
    """攔截對 LINE 的外部呼叫，讓指定的 sub 通過驗證。

    ⚠️ line_auth.py 是 `import httpx`，因此 `app.services.line_auth.httpx`
    與全域的 `httpx` 是同一個模組物件——patch 它的 AsyncClient 等於**全域
    替換 httpx.AsyncClient**，連本測試自己的 ASGI client 都會被換掉，
    導致請求根本沒進到應用程式就被 MockTransport 回應。

    故此處只在呼叫端**未自行指定 transport** 時才注入 mock：
    line_auth 內部是 `httpx.AsyncClient(timeout=10.0)`（無 transport）→ 攔截；
    測試自己的 client 明確帶 ASGITransport → 不受影響。
    這讓攔截與 client 的建立順序無關。
    """

    def install(sub: str):
        def handler(request: httpx.Request) -> httpx.Response:
            if "token" in str(request.url):
                return httpx.Response(200, json={"id_token": "id-token-from-code"})
            return httpx.Response(200, json={"sub": sub, "name": "測試使用者"})

        mock_transport = httpx.MockTransport(handler)
        original = httpx.AsyncClient

        class Patched(original):
            def __init__(self, *args, **kwargs):
                if "transport" not in kwargs:
                    kwargs["transport"] = mock_transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr("app.services.line_auth.httpx.AsyncClient", Patched)

    return install


async def _login_via_liff(client) -> None:
    async with client() as ac:
        response = await ac.post("/api/v1/auth/line/liff", json={"id_token": "t"})
    assert response.status_code == 200


def _role_of(db_session: Session, sub: str) -> str:
    user = db_session.query(User).filter(User.line_user_id == sub).one()
    return user.role


async def test_allowlisted_line_id_becomes_admin_on_login(client, line_api, allowlist, db_session):
    """FR-006：名單內的帳號登入後即取得管理員角色。"""
    allowlist(ADMIN_SUB)
    line_api(ADMIN_SUB)

    await _login_via_liff(client)

    assert _role_of(db_session, ADMIN_SUB) == ROLE_ADMIN


async def test_non_allowlisted_line_id_stays_normal_user(client, line_api, allowlist, db_session):
    allowlist(ADMIN_SUB)
    line_api(NORMAL_SUB)

    await _login_via_liff(client)

    assert _role_of(db_session, NORMAL_SUB) == ROLE_USER


async def test_role_is_revoked_on_next_login_after_removal_from_allowlist(
    client, line_api, allowlist, db_session
):
    """★ FR-007：自名單移除後，下次登入必須降回一般使用者。

    這是整個指派機制唯一的撤銷路徑。若 upsert_user() 寫成只升不降，
    此測試會失敗——而手動測試幾乎不會涵蓋這條路徑。
    """
    line_api(ADMIN_SUB)

    allowlist(ADMIN_SUB)
    await _login_via_liff(client)
    assert _role_of(db_session, ADMIN_SUB) == ROLE_ADMIN

    # 營運方把該帳號移出名單並重啟後端。
    allowlist("")
    await _login_via_liff(client)

    assert _role_of(db_session, ADMIN_SUB) == ROLE_USER, "移出名單後再次登入仍是管理員"


async def test_direct_database_grant_is_overwritten_by_allowlist(
    client, line_api, allowlist, db_session
):
    """★ 記錄一個反直覺但重要的後果：資料庫直接授予 admin 無效。

    名單是單一真實來源，故下次登入會覆寫。這不是缺陷而是設計結果——
    但維運上若不知道，會出現「我明明改了資料庫卻沒用」的困惑。
    quickstart.md 第 3 節有對應的操作說明。
    """
    allowlist("")
    line_api(NORMAL_SUB)
    await _login_via_liff(client)

    # 有人直接在資料庫把角色改成管理員。
    user = db_session.query(User).filter(User.line_user_id == NORMAL_SUB).one()
    user.role = ROLE_ADMIN
    db_session.flush()

    await _login_via_liff(client)

    assert _role_of(db_session, NORMAL_SUB) == ROLE_USER, (
        "資料庫直改應於下次登入被名單覆寫；若此處為 admin，代表名單不再是單一真實來源"
    )


async def test_both_entries_assign_the_same_role(client, line_api, allowlist, db_session):
    """憲章原則 I：角色判定不因登入入口而異。"""
    allowlist(ADMIN_SUB)
    line_api(ADMIN_SUB)

    async with client() as ac:
        liff = await ac.post("/api/v1/auth/line/liff", json={"id_token": "t"})
        web = await ac.post(
            "/api/v1/auth/line/callback",
            json={"code": "c", "redirect_uri": "http://localhost:3000/auth/callback", "state": "s"},
        )

    assert liff.status_code == 200
    assert web.status_code == 200
    # 同一 LINE 身分不論入口都是同一位使用者、同一個角色。
    assert liff.json()["user"]["id"] == web.json()["user"]["id"]
    # 以 line_user_id 過濾而非全表計數——測試資料庫可能有其他已提交的
    # 使用者（seed 腳本、冒煙測試），全表計數會讓本測試因無關資料而失敗。
    assert db_session.query(User).filter(User.line_user_id == ADMIN_SUB).count() == 1
    assert _role_of(db_session, ADMIN_SUB) == ROLE_ADMIN


async def test_login_response_does_not_expose_role(client, line_api, allowlist):
    """登入回應不夾帶角色資訊。

    前端要判斷是否為管理員，一律呼叫 /admin/me（research R-11）——讓權限
    判斷只有後端一套實作。若哪天為了方便把 role 塞進登入回應，前端就會
    出現與後端平行的第二套判斷。
    """
    allowlist(ADMIN_SUB)
    line_api(ADMIN_SUB)

    async with client() as ac:
        response = await ac.post("/api/v1/auth/line/liff", json={"id_token": "t"})

    assert "role" not in response.json()["user"]
    assert "admin" not in response.text.lower()
