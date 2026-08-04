"""查詢管線的單元測試（tasks.md T015）。

這裡驗的是 research.md R-04／data-model.md「查詢管線」所定的**順序**——
本輪最容易寫錯、且錯了不會拋任何例外的地方。

刻意不使用資料庫：以假的 Session 提供 Store 物件，讓管線邏輯能在沒有
PostgreSQL 的環境下完整驗證。真實資料庫行為由 integration 測試涵蓋。
"""

import uuid
from decimal import Decimal

import pytest

from app.services.stores import list_stores

TAIPEI_LAT, TAIPEI_LNG = 25.0478, 121.5170

#: 0.001 緯度約 111 公尺。
DEG_PER_KM = 1 / 111.0


class _FakeStore:
    """只帶管線需要的欄位，避免依賴 SQLAlchemy 的 declarative 機制。"""

    def __init__(self, name, lat, lng):
        self.id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}|{lat}|{lng}")
        self.name = name
        self.address = f"{name} 的地址"
        self.latitude = None if lat is None else Decimal(str(lat))
        self.longitude = None if lng is None else Decimal(str(lng))


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self, _stmt):
        return _FakeScalars(self._rows)


def _store_at_km(name: str, km: float) -> _FakeStore:
    """在參考點正北方 km 公里處建一家店。"""
    return _FakeStore(name, TAIPEI_LAT + km * DEG_PER_KM, TAIPEI_LNG)


def _names(result) -> list[str]:
    return [store.name for store, _ in result]


# ---------------------------------------------------------------------------
# (a) NULL 座標必須排除，且不得被當作 (0, 0)
# ---------------------------------------------------------------------------


def test_null_coordinates_excluded_from_nearby():
    stores = [
        _store_at_km("近店", 1.0),
        _FakeStore("無座標店", None, None),
    ]
    _, _, _, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert _names(result) == ["近店"]


def test_null_coordinates_not_treated_as_zero_zero():
    """(0,0) 距台北約 12,000 公里，若被當成座標會落在半徑外而『剛好』消失。

    因此改以「半徑放大到涵蓋整個地球」來確認它是被**排除**，而不是被
    距離過濾掉的——兩者在預設半徑下無法區分。
    """
    stores = [_FakeStore("無座標店", None, None)]
    _, _, total, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert result == []
    # 但它仍計入總數——total 要回答「資料庫裡有沒有店家」。
    assert total == 1


def test_store_with_only_latitude_is_excluded():
    """寫入端保證座標成對，但讀取端的防禦性檢查仍須有效。"""
    stores = [_FakeStore("半套座標店", TAIPEI_LAT, None)]
    _, _, _, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert result == []


# ---------------------------------------------------------------------------
# (b) 半徑邊界
# ---------------------------------------------------------------------------


def test_store_just_inside_radius_is_included():
    stores = [_store_at_km("4.9 公里店", 4.9)]
    _, radius, _, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert radius == 5.0
    assert _names(result) == ["4.9 公里店"]


def test_store_just_outside_radius_is_excluded():
    stores = [_store_at_km("5.1 公里店", 5.1)]
    _, _, _, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert result == []


# ---------------------------------------------------------------------------
# (c)(d) 筆數上限：超過要截斷，不足**不得**以範圍外的店家補足
# ---------------------------------------------------------------------------


def test_truncates_to_ten_when_more_than_ten_within_radius():
    stores = [_store_at_km(f"店{i:02d}", 0.2 * i) for i in range(1, 13)]  # 12 家，皆 < 5km
    _, _, _, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert len(result) == 10
    assert _names(result) == [f"店{i:02d}" for i in range(1, 11)]


def test_does_not_backfill_with_stores_outside_radius():
    """FR-020 明文禁止以超出範圍的店家補足名額。

    範圍內只有 3 家，範圍外有 20 家——結果必須是 3 筆，不是 10 筆。
    """
    near = [_store_at_km(f"近{i}", 1.0 + i) for i in range(3)]  # 1, 2, 3 km
    far = [_store_at_km(f"遠{i}", 10.0 + i) for i in range(20)]
    _, _, _, result = list_stores(_FakeSession(near + far), TAIPEI_LAT, TAIPEI_LNG)

    assert len(result) == 3
    assert all(name.startswith("近") for name in _names(result))


def test_radius_filter_applied_before_limit():
    """若順序寫反（先取 10 再過濾半徑），這裡會得到少於 3 筆。

    前 10 名依距離排序恰好都在範圍外，範圍內的 3 家排在第 11-13 位。
    """
    far = [_store_at_km(f"遠{i:02d}", 6.0 + i * 0.1) for i in range(10)]
    near = [_store_at_km(f"近{i}", 1.0 + i) for i in range(3)]
    _, _, _, result = list_stores(_FakeSession(far + near), TAIPEI_LAT, TAIPEI_LNG)

    assert len(result) == 3


# ---------------------------------------------------------------------------
# (e) 排序正確性（SC-002）
# ---------------------------------------------------------------------------


def test_sorted_by_distance_ascending():
    stores = [
        _store_at_km("遠", 4.0),
        _store_at_km("近", 0.5),
        _store_at_km("中", 2.0),
    ]
    _, _, _, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert _names(result) == ["近", "中", "遠"]
    distances = [d for _, d in result]
    assert distances == sorted(distances)


def test_distance_returned_in_metres():
    stores = [_store_at_km("兩公里店", 2.0)]
    _, _, _, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    _, distance_m = result[0]
    assert isinstance(distance_m, int)
    assert distance_m == pytest.approx(2000, abs=60)


# ---------------------------------------------------------------------------
# (f) total_store_count 不受任何過濾影響（R-05）
# ---------------------------------------------------------------------------


def test_total_count_ignores_radius_limit_and_null_coords():
    stores = (
        [_store_at_km(f"近{i:02d}", 0.2 * i) for i in range(1, 13)]  # 12 家在範圍內
        + [_store_at_km("遠", 50.0)]  # 1 家在範圍外
        + [_FakeStore("無座標", None, None)]  # 1 家無座標
    )
    _, _, total, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert len(result) == 10  # 受半徑與上限影響
    assert total == 14  # 不受任何過濾影響


def test_empty_nearby_but_stores_exist():
    """『附近查無店家』：stores 空但 total > 0 → 前端提供「改看全部店家」。"""
    stores = [_store_at_km("很遠", 50.0)]
    _, _, total, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert result == []
    assert total == 1


def test_no_stores_at_all():
    """『目前尚無店家資料』：stores 空且 total == 0 → 不提供改看操作。"""
    _, _, total, result = list_stores(_FakeSession([]), TAIPEI_LAT, TAIPEI_LNG)

    assert result == []
    assert total == 0


# ---------------------------------------------------------------------------
# 全部模式（FR-017）
# ---------------------------------------------------------------------------


def test_all_mode_returns_every_store_including_those_without_coords():
    """定位被拒／失敗時的替代路徑——無座標的店家在此**必須**出現。"""
    stores = [
        _store_at_km("有座標", 1.0),
        _FakeStore("無座標", None, None),
        _store_at_km("很遠", 100.0),
    ]
    mode, radius, total, result = list_stores(_FakeSession(stores))

    assert mode == "all"
    assert radius is None
    assert total == 3
    assert len(result) == 3
    assert all(distance is None for _, distance in result)


def test_all_mode_sorted_by_name():
    """依 name 升冪（Unicode 碼位序）。

    spec 只要求「穩定且可預期」，不要求筆劃或拼音序——中文的語意排序需要
    定序表且各資料庫行為不一，不值得為一條降級路徑引入。此處以 ASCII 名稱
    斷言，避免測試本身對中文排序做出錯誤假設。
    """
    stores = [
        _FakeStore("Charlie", 25.0, 121.0),
        _FakeStore("Alpha", 25.0, 121.0),
        _FakeStore("Bravo", 25.0, 121.0),
    ]
    _, _, _, result = list_stores(_FakeSession(stores))

    assert _names(result) == ["Alpha", "Bravo", "Charlie"]


def test_all_mode_sort_is_stable_for_duplicate_names():
    """同名店家的相對順序需穩定（以 id 決勝），避免每次查詢順序浮動。"""
    stores = [_FakeStore("連鎖健康餐盒", 25.0, 121.0) for _ in range(2)]
    stores[0].id = uuid.UUID("00000000-0000-5000-8000-000000000002")
    stores[1].id = uuid.UUID("00000000-0000-5000-8000-000000000001")

    _, _, _, first = list_stores(_FakeSession(stores))
    _, _, _, second = list_stores(_FakeSession(stores))

    assert [s.id for s, _ in first] == [s.id for s, _ in second]


def test_all_mode_not_limited_to_ten():
    """全部模式不套用 10 筆上限。"""
    stores = [_store_at_km(f"店{i:02d}", 0.1 * i) for i in range(1, 16)]
    _, _, _, result = list_stores(_FakeSession(stores))

    assert len(result) == 15


def test_partial_coordinates_falls_back_to_all_mode():
    """只給 lat 不給 lng 時走全部模式（端點層會先擋下並回 422，此處為防禦）。"""
    stores = [_store_at_km("店", 1.0)]
    mode, _, _, _ = list_stores(_FakeSession(stores), TAIPEI_LAT, None)

    assert mode == "all"


# ---------------------------------------------------------------------------
# 同名店家不得去重（FR-016a）
# ---------------------------------------------------------------------------


def test_same_name_stores_are_not_deduplicated():
    stores = [
        _FakeStore("連鎖健康餐盒", TAIPEI_LAT + 0.005, TAIPEI_LNG),
        _FakeStore("連鎖健康餐盒", TAIPEI_LAT + 0.010, TAIPEI_LNG),
    ]
    _, _, total, result = list_stores(_FakeSession(stores), TAIPEI_LAT, TAIPEI_LNG)

    assert total == 2
    assert len(result) == 2
    assert len({store.id for store, _ in result}) == 2
