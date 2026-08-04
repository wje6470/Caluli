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


# ═══════════════════════════════════════════════════════════════════
# 餐點維護（tasks.md T027，spec US3）
#
# 最關鍵的兩項是「留空 ≠ 0」與「跨店家不連動」：
#   - 留空必須存成 NULL，不得以 0 代替。以 0 寫入會讓「店家未提供」與
#     「確實為 0」的區別在寫入當下永久喪失，無法事後還原。
#   - 不同店家的同名餐點各自獨立（憲章原則 V）。
# ═══════════════════════════════════════════════════════════════════


def _menu_item(db_session: Session, store: Store, **overrides) -> MenuItem:
    payload = {"store_id": store.id, "name": "招牌餐點", "calories": 500} | overrides
    item = MenuItem(**payload)
    db_session.add(item)
    db_session.flush()
    db_session.refresh(item)
    return item


async def test_create_menu_item_with_full_nutrition(client, auth, db_session):
    store = _store(db_session)

    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items",
            headers=auth,
            json={
                "name": "滷肉飯",
                "calories": 620,
                "protein_g": 18.5,
                "carbs_g": 88,
                "fat_g": 21.2,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "滷肉飯"
    assert body["store_id"] == str(store.id)
    assert float(body["calories"]) == pytest.approx(620)


async def test_create_menu_item_with_only_name(client, auth, db_session):
    """FR-032：四個營養欄位皆選填，且彼此獨立（不比照座標的成對規則）。"""
    store = _store(db_session)

    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items",
            headers=auth,
            json={"name": "尚未提供營養資訊的餐點"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["calories"] is None
    assert body["protein_g"] is None
    assert body["carbs_g"] is None
    assert body["fat_g"] is None


async def test_blank_nutrition_is_stored_as_null_not_zero(client, auth, db_session):
    """★ FR-032 的不可逆性保護：留空必須存成 NULL，不得以 0 代替。

    若實作把未填欄位補成 0，「店家未提供」與「確實為 0」就永遠分不出來，
    而且分不出來這件事在寫入當下就發生、事後無法還原。
    """
    store = _store(db_session)

    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items",
            headers=auth,
            json={"name": "只知道熱量", "calories": 500},
        )

    assert response.status_code == 201
    assert response.json()["protein_g"] is None, "留空被寫成了 0——語意已永久喪失"

    item = db_session.query(MenuItem).filter(MenuItem.name == "只知道熱量").one()
    assert item.protein_g is None
    assert item.calories is not None


async def test_zero_and_null_are_distinguishable(client, auth, db_session):
    """0 與 NULL 必須是兩種可區分的狀態（FR-032、FR-033）。"""
    store = _store(db_session)

    async with client as ac:
        zero = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items",
            headers=auth,
            json={"name": "零卡氣泡水", "calories": 0, "fat_g": 0},
        )

    assert zero.status_code == 201
    body = zero.json()
    # 0 要如實存為 0，不得被當成「沒填」而轉成 null。
    assert body["calories"] is not None
    assert float(body["calories"]) == 0
    assert float(body["fat_g"]) == 0
    # 沒送的欄位仍是 null。
    assert body["protein_g"] is None


@pytest.mark.parametrize("field", ["calories", "protein_g", "carbs_g", "fat_g"])
async def test_negative_nutrition_is_rejected(client, auth, db_session, field):
    store = _store(db_session)

    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items",
            headers=auth,
            json={"name": "負值餐點", field: -1},
        )

    assert response.status_code == 422
    assert db_session.query(MenuItem).count() == 0


async def test_non_numeric_nutrition_is_rejected(client, auth, db_session):
    store = _store(db_session)

    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items",
            headers=auth,
            json={"name": "餐點", "calories": "很多"},
        )

    assert response.status_code == 422
    assert db_session.query(MenuItem).count() == 0


@pytest.mark.parametrize("name", ["", "   "])
async def test_menu_item_name_is_required(client, auth, db_session, name):
    store = _store(db_session)

    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items", headers=auth, json={"name": name}
        )

    assert response.status_code == 422
    assert db_session.query(MenuItem).count() == 0


async def test_create_menu_item_under_missing_store_returns_404(client, auth, db_session):
    """FR-035：不得產生無所屬店家的餐點。"""
    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{uuid.uuid4()}/menu-items",
            headers=auth,
            json={"name": "孤兒餐點", "calories": 100},
        )

    assert response.status_code == 404
    assert db_session.query(MenuItem).count() == 0, "不得產生無所屬店家的餐點"


async def test_menu_item_list_is_scoped_to_its_store(client, auth, db_session):
    """FR-033：只列出所選店家的餐點，不得混入其他店家。"""
    store_a = _store(db_session, name="A 店")
    store_b = _store(db_session, name="B 店")
    _menu_item(db_session, store_a, name="A 的餐點")
    _menu_item(db_session, store_b, name="B 的餐點")

    async with client as ac:
        response = await ac.get(f"/api/v1/admin/stores/{store_a.id}/menu-items", headers=auth)

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["menu_items"]]
    assert names == ["A 的餐點"]


async def test_menu_item_list_of_missing_store_returns_404(client, auth):
    async with client as ac:
        response = await ac.get(f"/api/v1/admin/stores/{uuid.uuid4()}/menu-items", headers=auth)

    assert response.status_code == 404


async def test_empty_menu_returns_empty_list_not_error(client, auth, db_session):
    """FR-036：尚無餐點是正常狀態，不是錯誤。"""
    store = _store(db_session)

    async with client as ac:
        response = await ac.get(f"/api/v1/admin/stores/{store.id}/menu-items", headers=auth)

    assert response.status_code == 200
    assert response.json()["menu_items"] == []


async def test_update_menu_item(client, auth, db_session):
    store = _store(db_session)
    item = _menu_item(db_session, store, calories=500)

    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/menu-items/{item.id}", headers=auth, json={"calories": 650}
        )

    assert response.status_code == 200
    assert float(response.json()["calories"]) == pytest.approx(650)
    # 未提供的欄位維持原值。
    assert response.json()["name"] == "招牌餐點"


async def test_update_can_clear_a_nutrition_value_to_null(client, auth, db_session):
    """把已填的數值改回「未提供」是合法操作——例如發現先前登錄有誤。"""
    store = _store(db_session)
    item = _menu_item(db_session, store, protein_g=20)

    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/menu-items/{item.id}", headers=auth, json={"protein_g": None}
        )

    assert response.status_code == 200
    assert response.json()["protein_g"] is None


async def test_updating_one_store_menu_item_does_not_affect_another(client, auth, db_session):
    """★ FR-034／憲章原則 V：不同店家的同名餐點各自獨立。"""
    store_a = _store(db_session, name="A 店")
    store_b = _store(db_session, name="B 店")
    item_a = _menu_item(db_session, store_a, name="滷肉飯", calories=600)
    item_b = _menu_item(db_session, store_b, name="滷肉飯", calories=600)

    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/menu-items/{item_a.id}", headers=auth, json={"calories": 900}
        )

    assert response.status_code == 200
    db_session.refresh(item_b)
    assert float(item_b.calories) == 600, "修改 A 店餐點連動改到了 B 店的同名餐點"


async def test_update_missing_menu_item_returns_404(client, auth):
    async with client as ac:
        response = await ac.patch(
            f"/api/v1/admin/menu-items/{uuid.uuid4()}", headers=auth, json={"calories": 100}
        )

    assert response.status_code == 404


async def test_delete_menu_item_leaves_store_and_siblings_intact(client, auth, db_session):
    """FR-030：刪除餐點不影響店家本身與其餘餐點。"""
    store = _store(db_session)
    target = _menu_item(db_session, store, name="要刪的")
    _menu_item(db_session, store, name="要留的")

    async with client as ac:
        response = await ac.delete(f"/api/v1/admin/menu-items/{target.id}", headers=auth)

    assert response.status_code == 204
    assert db_session.query(Store).count() == 1
    remaining = db_session.query(MenuItem).all()
    assert [item.name for item in remaining] == ["要留的"]


async def test_delete_missing_menu_item_returns_404(client, auth):
    async with client as ac:
        response = await ac.delete(f"/api/v1/admin/menu-items/{uuid.uuid4()}", headers=auth)

    assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# JSON 原生型別護欄（2026-08-04 雙方定案：數值一律為 JSON number）
#
# ★ 為什麼需要獨立的 isinstance 斷言
# ==================================
# 本檔其餘測試用 float(body["calories"]) 做比較，而 float("620.00") 與
# float(620.0) **都會通過**——也就是說那些斷言完全擋不住「schema 改回
# Decimal、回應變成字串」這種退化。第二輪就是因為這個盲點才讓字串型別
# 一路走到前端，最後在 value.toFixed(1) 炸掉整頁。
#
# 故此處直接斷言 JSON 解析後的 Python 原生型別。
# ═══════════════════════════════════════════════════════════════════


async def test_store_numeric_fields_are_json_numbers_not_strings(client, auth, db_session):
    store = _store(db_session, latitude=25.0396, longitude=121.5679)

    async with client as ac:
        detail = await ac.get(f"/api/v1/admin/stores/{store.id}", headers=auth)
        listed = await ac.get("/api/v1/admin/stores", headers=auth)

    body = detail.json()
    assert isinstance(body["latitude"], float), (
        f"latitude 應為 JSON number，實得 {type(body['latitude'])}"
    )
    assert isinstance(body["longitude"], float)

    row = listed.json()["stores"][0]
    assert isinstance(row["latitude"], float)
    assert isinstance(row["menu_item_count"], int)


async def test_menu_item_numeric_fields_are_json_numbers_not_strings(client, auth, db_session):
    store = _store(db_session)
    item = _menu_item(db_session, store, calories=620, protein_g=18.5, carbs_g=88, fat_g=21.2)

    async with client as ac:
        listed = await ac.get(f"/api/v1/admin/stores/{store.id}/menu-items", headers=auth)
        updated = await ac.patch(
            f"/api/v1/admin/menu-items/{item.id}", headers=auth, json={"calories": 650}
        )

    row = listed.json()["menu_items"][0]
    for field in ("calories", "protein_g", "carbs_g", "fat_g"):
        assert isinstance(row[field], float), f"{field} 應為 JSON number，實得 {type(row[field])}"

    assert isinstance(updated.json()["calories"], float)


async def test_zero_stays_number_and_null_stays_null(client, auth, db_session):
    """型別調整後仍須維持：0 是 number、未提供是 JSON null（不是字串 "null"）。"""
    store = _store(db_session)

    async with client as ac:
        response = await ac.post(
            f"/api/v1/admin/stores/{store.id}/menu-items",
            headers=auth,
            json={"name": "零卡", "calories": 0},
        )

    body = response.json()
    assert isinstance(body["calories"], float)
    assert body["calories"] == 0
    assert body["protein_g"] is None
