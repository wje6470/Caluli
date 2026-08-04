"""店家與餐點端點的整合測試（tasks.md T018、T031、T044）。

需要真 PostgreSQL——conftest 在 Docker 與 TEST_DATABASE_URL 皆不可用時
會自動 skip，讓單元測試仍可跑。
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.db.models import MenuItem, Store, User
from app.db.session import get_db
from app.main import app

TAIPEI_LAT, TAIPEI_LNG = 25.0478, 121.5170
DEG_PER_KM = 1 / 111.0


@pytest.fixture(autouse=True)
def _isolate_store_tables(db_session):
    """在測試交易內清空店家資料。

    多數斷言針對絕對筆數（例如「恰 10 筆」「total_store_count == 0」），
    若資料庫中已有 seed 的測試店家就會失敗。db_session 於測試結束時
    rollback，因此這裡的刪除不會影響資料庫的既有內容——開發者可以在
    已 seed 的本機資料庫上直接跑測試，不需要另外準備一個乾淨的庫。
    """
    db_session.query(MenuItem).delete()
    db_session.query(Store).delete()
    db_session.flush()


@pytest.fixture
def client(db_session):
    """已登入的測試 client。

    覆寫 get_db 與 get_current_user——本輪不驗證登入流程本身（第一輪已涵蓋），
    只驗證端點確實**要求**登入。
    """
    user = User(line_user_id=f"U-test-{uuid.uuid4().hex[:8]}", display_name="測試使用者")
    db_session.add(user)
    db_session.flush()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db_session):
    """未登入的 client——只覆寫 get_db。"""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _add_store(db, name, km=None, address="測試地址"):
    """在參考點正北方 km 公里處新增店家；km 為 None 則不設座標。"""
    store = Store(
        name=name,
        address=address,
        latitude=None if km is None else Decimal(str(round(TAIPEI_LAT + km * DEG_PER_KM, 6))),
        longitude=None if km is None else Decimal(str(TAIPEI_LNG)),
    )
    db.add(store)
    db.flush()
    return store


# ---------------------------------------------------------------------------
# 附近模式（T018）
# ---------------------------------------------------------------------------


def test_nearby_returns_sorted_and_capped_at_ten(client, db_session):
    for i in range(1, 13):  # 12 家皆在 5 公里內
        _add_store(db_session, f"店{i:02d}", km=0.2 * i)

    r = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}&lng={TAIPEI_LNG}")
    assert r.status_code == 200
    body = r.json()

    assert body["mode"] == "nearby"
    assert body["radius_km"] == 5.0
    assert body["total_store_count"] == 12
    assert len(body["stores"]) == 10

    distances = [s["distance_m"] for s in body["stores"]]
    assert distances == sorted(distances)
    assert all(d is not None for d in distances)


def test_nearby_excludes_stores_without_coordinates(client, db_session):
    _add_store(db_session, "有座標", km=1.0)
    _add_store(db_session, "無座標", km=None)

    body = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}&lng={TAIPEI_LNG}").json()

    assert [s["name"] for s in body["stores"]] == ["有座標"]
    assert body["total_store_count"] == 2  # 仍計入總數


def test_nearby_does_not_backfill_beyond_radius(client, db_session):
    _add_store(db_session, "近", km=1.0)
    for i in range(15):
        _add_store(db_session, f"遠{i}", km=10.0 + i)

    body = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}&lng={TAIPEI_LNG}").json()

    assert len(body["stores"]) == 1
    assert body["stores"][0]["name"] == "近"


def test_requires_authentication(anon_client):
    assert anon_client.get("/api/v1/stores").status_code == 401


def test_partial_coordinates_rejected(client):
    """只給 lat 不給 lng 必須回 422，不得無聲退回全部模式。"""
    r = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}")
    assert r.status_code == 422

    r = client.get(f"/api/v1/stores?lng={TAIPEI_LNG}")
    assert r.status_code == 422


def test_out_of_range_coordinates_rejected(client):
    assert client.get("/api/v1/stores?lat=999&lng=0").status_code == 422
    assert client.get("/api/v1/stores?lat=0&lng=999").status_code == 422


# ---------------------------------------------------------------------------
# 三種空狀態（T044）—— 少了 total_store_count 就無從分辨
# ---------------------------------------------------------------------------


def test_empty_nearby_but_stores_exist(client, db_session):
    """『附近查無店家』：前端據此提供「改看全部店家」。"""
    _add_store(db_session, "很遠的店", km=50.0)

    body = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}&lng={TAIPEI_LNG}").json()

    assert body["stores"] == []
    assert body["total_store_count"] == 1


def test_no_stores_at_all(client):
    """『目前尚無店家資料』：前端不提供改看操作。"""
    body = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}&lng={TAIPEI_LNG}").json()

    assert body["stores"] == []
    assert body["total_store_count"] == 0


def test_all_mode_shape(client, db_session):
    _add_store(db_session, "有座標", km=1.0)
    _add_store(db_session, "無座標", km=None)
    _add_store(db_session, "很遠", km=100.0)

    body = client.get("/api/v1/stores").json()

    assert body["mode"] == "all"
    assert body["radius_km"] is None
    assert len(body["stores"]) == 3  # 無座標與超遠的店家在此都要出現
    assert all(s["distance_m"] is None for s in body["stores"])


# ---------------------------------------------------------------------------
# 店家與餐點（T031）
# ---------------------------------------------------------------------------


def test_get_store_not_found(client):
    r = client.get(f"/api/v1/stores/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_menu_items_of_missing_store_is_404(client):
    r = client.get(f"/api/v1/stores/{uuid.uuid4()}/menu-items")
    assert r.status_code == 404


def test_store_without_menu_items_returns_200_and_empty_list(client, db_session):
    """空清單是正常結果，不是錯誤——回 200 而非 404（FR-024）。"""
    store = _add_store(db_session, "沒有餐點的店", km=1.0)

    r = client.get(f"/api/v1/stores/{store.id}/menu-items")

    assert r.status_code == 200
    assert r.json()["menu_items"] == []


def test_null_and_zero_nutrition_are_preserved_distinctly(client, db_session):
    """FR-025 的資料層驗證：null 與 0 不得互相正規化。

    這是前端能正確顯示「無資料」vs「0」的前提——若 API 這一層就把 null
    轉成 0（或反之），前端再怎麼寫都不可能正確。
    """
    store = _add_store(db_session, "營養值測試店", km=1.0)
    db_session.add(
        MenuItem(store_id=store.id, name="未提供", calories=None, protein_g=None,
                 carbs_g=None, fat_g=None)
    )
    db_session.add(
        MenuItem(store_id=store.id, name="零卡", calories=Decimal("0"),
                 protein_g=Decimal("0"), carbs_g=Decimal("0"), fat_g=Decimal("0"))
    )
    db_session.flush()

    body = client.get(f"/api/v1/stores/{store.id}/menu-items").json()
    items = {i["name"]: i for i in body["menu_items"]}

    assert items["未提供"]["calories_kcal"] is None
    assert items["未提供"]["protein_g"] is None

    assert items["零卡"]["calories_kcal"] is not None
    assert float(items["零卡"]["calories_kcal"]) == 0.0
    assert float(items["零卡"]["fat_g"]) == 0.0


def test_numeric_fields_are_json_numbers_not_strings(client, db_session):
    """★ 數值欄位在 JSON 中必須是 number，不能是 string。

    contracts/openapi.yaml 宣告 `type: number`，前端型別也是 `number`。
    若 schema 改用 Decimal，Pydantic v2 會序列化成字串（"650.00"），
    前端任何 `value.toFixed()` 都會拋 TypeError——這個 bug 實際發生過
    （MenuItemRow 崩潰）。

    這支測試直接斷言 JSON 的原生型別，是防止改回 Decimal 的唯一護欄：
    用 float(x) 或 == 比較都會被字串矇混過去。
    """
    store = _add_store(db_session, "型別測試店", km=1.0)
    db_session.add(
        MenuItem(
            store_id=store.id,
            name="一般餐點",
            calories=Decimal("650.00"),
            protein_g=Decimal("25.00"),
            carbs_g=Decimal("80.00"),
            fat_g=Decimal("24.00"),
        )
    )
    db_session.flush()

    # --- 店家清單：座標與距離 ---
    body = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}&lng={TAIPEI_LNG}").json()
    s = body["stores"][0]
    assert isinstance(s["latitude"], float), f"latitude 應為 number，實際 {type(s['latitude'])}"
    assert isinstance(s["longitude"], float), f"longitude 應為 number，實際 {type(s['longitude'])}"
    assert isinstance(s["distance_m"], int), f"distance_m 應為整數，實際 {type(s['distance_m'])}"
    assert isinstance(body["total_store_count"], int)
    assert isinstance(body["radius_km"], float)

    # --- 餐點：四個營養欄位 ---
    items = client.get(f"/api/v1/stores/{store.id}/menu-items").json()["menu_items"]
    item = items[0]
    for field in ("calories_kcal", "protein_g", "carbs_g", "fat_g"):
        assert isinstance(item[field], float), (
            f"{field} 應為 number，實際 {type(item[field])} = {item[field]!r}。"
            "schema 若用 Decimal，Pydantic 會序列化成字串而讓前端 toFixed 崩潰。"
        )
    assert item["calories_kcal"] == 650.0


def test_zero_stays_number_and_null_stays_null_on_the_wire(client, db_session):
    """0 與 null 在 JSON 中的型別也必須正確（FR-025 的傳輸層前提）。"""
    store = _add_store(db_session, "零值型別店", km=1.0)
    db_session.add(
        MenuItem(store_id=store.id, name="零卡", calories=Decimal("0"), protein_g=Decimal("0"))
    )
    db_session.flush()

    item = client.get(f"/api/v1/stores/{store.id}/menu-items").json()["menu_items"][0]

    assert isinstance(item["calories_kcal"], float)
    assert item["calories_kcal"] == 0.0
    assert item["carbs_g"] is None  # 未設定 → null，不是 0


def test_same_name_menu_items_not_deduplicated(client, db_session):
    store = _add_store(db_session, "同名餐點店", km=1.0)
    for _ in range(2):
        db_session.add(MenuItem(store_id=store.id, name="招牌便當", calories=Decimal("700")))
    db_session.flush()

    items = client.get(f"/api/v1/stores/{store.id}/menu-items").json()["menu_items"]

    assert len(items) == 2
    assert len({i["id"] for i in items}) == 2


def test_same_name_stores_are_distinct_entities(client, db_session):
    """連鎖分店同名——以 id 識別、以地址區分，不得合併（FR-016a）。"""
    a = _add_store(db_session, "連鎖健康餐盒", km=1.0, address="公園路 30 號")
    b = _add_store(db_session, "連鎖健康餐盒", km=2.0, address="承德路 55 號")
    db_session.add(MenuItem(store_id=a.id, name="A 店限定", calories=Decimal("500")))
    db_session.add(MenuItem(store_id=b.id, name="B 店限定", calories=Decimal("600")))
    db_session.flush()

    body = client.get(f"/api/v1/stores?lat={TAIPEI_LAT}&lng={TAIPEI_LNG}").json()
    assert len(body["stores"]) == 2
    assert {s["address"] for s in body["stores"]} == {"公園路 30 號", "承德路 55 號"}

    a_items = client.get(f"/api/v1/stores/{a.id}/menu-items").json()["menu_items"]
    assert [i["name"] for i in a_items] == ["A 店限定"]


def test_deleting_store_cascades_to_menu_items(client, db_session):
    """實刪除且連帶刪除餐點（2026-08-04 交接確認），不留孤兒資料。"""
    store = _add_store(db_session, "即將刪除的店", km=1.0)
    db_session.add(MenuItem(store_id=store.id, name="餐點", calories=Decimal("100")))
    db_session.flush()
    store_id = store.id

    db_session.delete(store)
    db_session.flush()

    assert db_session.get(Store, store_id) is None
    remaining = db_session.query(MenuItem).filter(MenuItem.store_id == store_id).count()
    assert remaining == 0
