"""登入整合測試（tasks.md T067）。

★ 憲章原則 I 的核心驗證：兩個入口收斂至同一驗證核心，且同一 LINE 身分
  不論從哪個入口登入都對應同一位使用者（FR-006、FR-007、SC-006）。
"""

import uuid

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import ROLE_USER, HealthProfile, User
from app.db.session import get_db
from app.main import app

LINE_SUB = "U0123456789abcdef0123456789abcdef"
VERIFY_PAYLOAD = {"sub": LINE_SUB, "name": "陳小明", "picture": "https://example.com/a.jpg"}


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    yield httpx.AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


@pytest.fixture
def line_api(monkeypatch):
    """攔截對 LINE 的外部呼叫。calls 記錄實際打了哪些端點。"""
    calls: list[str] = []

    def install(*, verify_status: int = 200, verify_body: dict | None = None):
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "token" in str(request.url):
                return httpx.Response(200, json={"id_token": "id-token-from-code"})
            return httpx.Response(verify_status, json=verify_body or VERIFY_PAYLOAD)

        transport = httpx.MockTransport(handler)

        class Patched(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr("app.services.line_auth.httpx.AsyncClient", Patched)
        return calls

    return install


async def test_liff_login_creates_user_and_returns_session(client, line_api, db_session):
    line_api()
    async with client as ac:
        response = await ac.post("/api/v1/auth/line/liff", json={"id_token": "liff-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] > 0
    # 首次登入尚無 profile，前端須據此導向 onboarding（FR-013）。
    assert body["profile_completed"] is False
    assert body["user"]["display_name"] == "陳小明"

    user = db_session.query(User).one()
    assert user.line_user_id == LINE_SUB
    # 本輪所有使用者皆為一般使用者（憲章原則 IV）。
    assert user.role == ROLE_USER

    # 簽發的是本站 token，不是 LINE 的 token。
    assert decode_access_token(body["access_token"]) == user.id


async def test_web_oauth_login_exchanges_code_then_uses_same_core(client, line_api, db_session):
    calls = line_api()
    async with client as ac:
        response = await ac.post(
            "/api/v1/auth/line/callback",
            json={
                "code": "auth-code",
                "redirect_uri": "http://localhost:3000/auth/callback",
                "state": "s",
            },
        )

    assert response.status_code == 200
    # 網頁入口多一次 code → token 交換，之後仍走同一支驗證端點。
    assert any("token" in url for url in calls)
    assert any("verify" in url for url in calls)
    assert db_session.query(User).count() == 1


async def test_both_entries_map_to_the_same_user(client, line_api, db_session):
    """★ 同一 LINE 身分從兩個入口登入 = 同一位使用者、同一份資料。"""
    line_api()
    async with client as ac:
        liff = await ac.post("/api/v1/auth/line/liff", json={"id_token": "liff-token"})
        web = await ac.post(
            "/api/v1/auth/line/callback",
            json={
                "code": "auth-code",
                "redirect_uri": "http://localhost:3000/auth/callback",
                "state": "s",
            },
        )

    assert liff.json()["user"]["id"] == web.json()["user"]["id"]
    assert db_session.query(User).count() == 1, "不得因入口不同而建立兩位使用者"


async def test_login_response_contains_no_entry_point_information(client, line_api):
    """回應結構不得洩漏來源入口——否則下游會開始依入口分岔。"""
    line_api()
    async with client as ac:
        liff = await ac.post("/api/v1/auth/line/liff", json={"id_token": "t"})
        web = await ac.post(
            "/api/v1/auth/line/callback",
            json={"code": "c", "redirect_uri": "http://localhost:3000/auth/callback", "state": "s"},
        )

    assert liff.json().keys() == web.json().keys()
    serialized = liff.text.lower()
    for leaked in ("liff", "entry", "source", "oauth"):
        assert leaked not in serialized


async def test_invalid_id_token_returns_401(client, line_api):
    line_api(verify_status=400, verify_body={"error": "invalid_request"})
    async with client as ac:
        response = await ac.post("/api/v1/auth/line/liff", json={"id_token": "bogus"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_existing_profile_reports_completed(client, line_api, db_session):
    from decimal import Decimal

    line_api()
    async with client as ac:
        first = await ac.post("/api/v1/auth/line/liff", json={"id_token": "t"})
        user_id = uuid.UUID(first.json()["user"]["id"])

        db_session.add(
            HealthProfile(
                user_id=user_id,
                gender="male",
                age_years=28,
                height_cm=Decimal("175"),
                weight_kg=Decimal("68.5"),
                activity_level="moderate",
                bmr_kcal=Decimal("1643.75"),
                tdee_kcal=Decimal("2383.44"),
                target_protein_g=Decimal("123.3"),
                target_carbs_g=Decimal("323.6"),
                target_fat_g=Decimal("66.2"),
            )
        )
        db_session.flush()
        db_session.expire_all()

        second = await ac.post("/api/v1/auth/line/liff", json={"id_token": "t"})

    # 已建檔者再次登入應直接進儀表板，不重複要求填寫（US1 情境 5）。
    assert second.json()["profile_completed"] is True


async def test_unauthenticated_request_to_me_returns_401(client):
    async with client as ac:
        response = await ac.get("/api/v1/me")
    assert response.status_code == 401
