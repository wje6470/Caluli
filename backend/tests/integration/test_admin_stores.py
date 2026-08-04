"""後台店家 CRUD（tasks.md T018，spec US2）。

涵蓋 spec 明列的邊界情境，重點在**寫入端的資料正確性**——這張表由第二輪
讀取，寫壞了對方查到的就是壞資料。

四項邊界值得特別注意（都是 spec 點名的）：
  - 只填單一座標值 → 拒絕（FR-022）
  - 座標超出地理範圍 → 拒絕（FR-023）
  - 店家同名不同址 → 允許（FR-027，連鎖分店）
  - 對已刪除的店家操作 → 404 而非通用錯誤（FR-028）
"""

import uuid

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import ROLE_ADMIN, MenuItem, Store, User
from app.db.session import get_db
from app.main import app

ADMIN_SUB = "U33333333333333333333333333333333"


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    yield httpx.AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


@pytest.fixture
def auth(db_session: Session) -> dict[str, str]:
    user = User(line_user_id=ADMIN_SUB, display_name="測試管理員", role=ROLE_ADMIN)
    db_session.add(user)
    db_session.flush()
    token, _ = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


def _store(db_session: Session, **overrides) -> Store:
    payload = {"name": "測試店家", "address": "台北市信義區"} | overrides
    store = Store(**payload)
    db_session.add(store)
    db_session.flush()
    db_session.refresh(store)
    return store


# ─── 建立 ────────────────────────────────────────────────────────────


async def test_create_store_with_full_data(client, auth, db_session):
    async with client as ac:
        response = await ac.post(
            "/api/v1/admin/stores",
            headers=auth,
            json={
                "name": "鼎泰豐 信義店",
                "address": "台北市信義區松高路 11 號",
                "latitude": 25.0396,
                "longitude": 121.5679,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "鼎泰豐 信義店"
    assert float(body["latitude"]) == pytest.approx(25.0396)
    assert db_session.query(Store).count() == 1


async def test_create_store_without_coordinates_is_allowed(client, auth, db_session):
    """FR-021：座標選填——允許先建名稱地址，之後再補座標。"""
    async with client as ac:
        response = await ac.post(
            "/api/v1/admin/stores",
            headers=auth,
            json={"name": "待補座標店", "address": "台北市大安區"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["latitude"] is None
    assert body["longitude"] is None


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"name": "", "address": "台北市"}, "名稱空白"),
        ({"name": "   ", "address": "台北市"}, "名稱只有空白"),
        ({"address": "台北市"}, "缺名稱"),
        ({"name": "店", "address": ""}, "地址空白"),
        ({"name": "店"}, "缺地址"),
    ],
)
async def test_create_store_rejects_missing_required_fields(
    client, auth, db_session, payload, reason
):
    async with client as ac:
        response = await ac.post("/api/v1/admin/stores", headers=auth, json=payload)

    assert response.status_code == 422, reason
    assert db_session.query(Store).count() == 0, f"{reason}：不得建立任何資料"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "店", "address": "台北市", "latitude": 25.0},
        {"name": "店", "address": "台北市", "longitude": 121.5},
        {"name": "店", "address": "台北市", "latitude": 25.0, "longitude": None},
        {"name": "店", "address": "台北市", "latitude": None, "longitude": 121.5},
    ],
    ids=["only-lat", "only-lng", "lat-with-null-lng", "null-lat-with-lng"],
)
async def test_create_store_rejects_unpaired_coordinates(client, auth, db_session, payload):
    """★ FR-022：座標必須成對。

    只有單一座標值的店家對第二輪毫無意義——無法計算距離，卻又不是明確的
    「未設定座標」。
    """
    async with client as ac:
        response = await ac.post("/api/v1/admin/stores", headers=auth, json=payload)

    assert response.status_code == 422
    assert db_session.query(Store).count() == 0


@pytest.mark.parametrize(
    ("lat", "lng"),
    [(91, 121.5), (-91, 121.5), (25.0, 181), (25.0, -181)],
    ids=["lat-too-high", "lat-too-low", "lng-too-high", "lng-too-low"],
)
async def test_create_store_rejects_out_of_range_coordinates(client, auth, db_session, lat, lng):
    """FR-023：緯度 -90～90、經度 -180～180。"""
    async with client as ac:
        response = await ac.post(
            "/api/v1/admin/stores",
            headers=auth,
            json={"name": "店", "address": "台北市", "latitude": lat, "longitude": lng},
        )

    assert response.status_code == 422
    assert db_session.query(Store).count() == 0


async def test_duplicate_store_name_is_allowed(client, auth, db_session):
    """FR-027：連鎖分店同名為正常資料，以地址區分。"""
    _store(db_session, name="鼎泰豐", address="台北市信義區")

    async with client as ac:
        response = await ac.post(
            "/api/v1/admin/stores",
            headers=auth,
            json={"name": "鼎泰豐", "address": "台北市中山區"},
        )

    assert response.status_code == 201
    assert db_session.query(Store).count() == 2


# ─── 查詢 ────────────────────────────────────────────────────────────


async def test_list_stores_includes_menu_item_count(client, auth, db_session):
    """FR-038 的前提：刪除確認要能顯示「將一併刪除 N 道餐點」。"""
    with_items = _store(db_session, name="有餐點的店")
    _store(db_session, name="沒餐點的店")
    for i in range(3):
        db_session.add(MenuItem(store_id=with_items.id, name=f"餐點{i}", calories=100))
    db_session.flush()

    async with client as ac:
        response = await ac.get("/api/v1/admin/stores", headers=auth)

    assert response.status_code == 200
    counts = {s["name"]: s["menu_item_count"] for s in response.json()["stores"]}
    assert counts == {"有餐點的店": 3, "沒餐點的店": 0}


async def test_get_missing_store_returns_404(client, auth):
    async with client as ac:
        response = await ac.get(f"/api/v1/admin/stores/{uuid.uuid4()}", headers=auth)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ─── 更新 ────────────────────────────────────────────────────────────


async def test_update_store_fields(client, auth, db_session):
    store = _store(db_session)

    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/stores/{store.id}",
            headers=auth,
            json={"address": "台北市中正區新地址"},
        )

    assert response.status_code == 200
    assert response.json()["address"] == "台北市中正區新地址"
    # 未提供的欄位維持原值。
    assert response.json()["name"] == "測試店家"


async def test_backfilling_coordinates_clears_the_missing_state(client, auth, db_session):
    """US2 情境 8：補上座標後，該店家即可進入依距離排序的結果。"""
    store = _store(db_session, name="待補座標店")
    assert store.latitude is None

    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/stores/{store.id}",
            headers=auth,
            json={"latitude": 25.0330, "longitude": 121.5654},
        )

    assert response.status_code == 200
    assert response.json()["latitude"] is not None
    assert response.json()["longitude"] is not None


async def test_update_rejects_unpairing_coordinates(client, auth, db_session):
    """★ 部分更新的成對規則以「套用後的最終狀態」判定。

    原本有完整座標，只送 latitude=null 會讓最終狀態變成不成對——
    若實作只檢查本次請求帶了哪些欄位，這裡就會漏掉。
    """
    store = _store(db_session, latitude=25.0, longitude=121.5)

    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/stores/{store.id}", headers=auth, json={"latitude": None}
        )

    assert response.status_code == 422
    db_session.refresh(store)
    assert store.latitude is not None, "被拒的請求不得造成任何變更"


async def test_update_can_clear_both_coordinates_together(client, auth, db_session):
    """成對清除是合法的——等同把店家改回「未設定座標」。"""
    store = _store(db_session, latitude=25.0, longitude=121.5)

    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/stores/{store.id}",
            headers=auth,
            json={"latitude": None, "longitude": None},
        )

    assert response.status_code == 200
    assert response.json()["latitude"] is None
    assert response.json()["longitude"] is None


async def test_update_missing_store_returns_404(client, auth):
    """FR-028：對已被其他管理員刪除的店家操作，需明確回報而非通用錯誤。"""
    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/stores/{uuid.uuid4()}", headers=auth, json={"name": "新名稱"}
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ─── 刪除 ────────────────────────────────────────────────────────────


async def test_delete_store(client, auth, db_session):
    store = _store(db_session)

    async with client as ac:
        response = await ac.delete(f"/api/v1/admin/stores/{store.id}", headers=auth)

    assert response.status_code == 204
    assert db_session.query(Store).count() == 0


async def test_delete_missing_store_returns_404(client, auth):
    async with client as ac:
        response = await ac.delete(f"/api/v1/admin/stores/{uuid.uuid4()}", headers=auth)

    assert response.status_code == 404


async def test_deleting_store_cascades_to_its_menu_items(client, auth, db_session):
    """★ FR-037／FR-040：刪除店家連帶刪除其餐點，不留孤兒資料。

    刪除為實刪除且無法還原，故這條路徑必須有自動化保護。必須跑在真
    PostgreSQL 上——ON DELETE CASCADE 是資料庫層行為，SQLite 預設連外鍵
    約束都不啟用，換掉資料庫等於沒測到。

    另一家店的餐點必須不受影響，否則 cascade 的範圍就出錯了。
    """
    target = _store(db_session, name="要刪除的店")
    bystander = _store(db_session, name="不該受影響的店")
    for i in range(3):
        db_session.add(MenuItem(store_id=target.id, name=f"餐點{i}", calories=100))
    db_session.add(MenuItem(store_id=bystander.id, name="旁觀者餐點", calories=200))
    db_session.flush()

    target_id, bystander_id = target.id, bystander.id
    assert db_session.query(MenuItem).filter(MenuItem.store_id == target_id).count() == 3

    async with client as ac:
        response = await ac.delete(f"/api/v1/admin/stores/{target_id}", headers=auth)

    assert response.status_code == 204
    assert db_session.query(MenuItem).filter(MenuItem.store_id == target_id).count() == 0
    # 其他店家的餐點完好。
    assert db_session.query(MenuItem).filter(MenuItem.store_id == bystander_id).count() == 1
    assert db_session.query(Store).count() == 1
