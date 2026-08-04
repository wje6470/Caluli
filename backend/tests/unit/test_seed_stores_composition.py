"""測試資料的組成稽核（tasks.md T009）。

seed 的每一組資料都對應一個驗收情境，缺一項就有情境驗不到。這支測試在
**不需要資料庫**的情況下確認組成正確——否則「seed 少了一筆」這種問題只會
在手動驗證走到那一步時才發現，而那通常是最後才做的事。
"""

from decimal import Decimal

from app.core.config import get_settings
from app.scripts.seed_stores import (
    REFERENCE_POINT,
    TEST_PREFIX,
    _build_rows,
    _menu_for,
    _store_id,
)
from app.services.geo import haversine_km

RADIUS_KM = get_settings().nearby_radius_km
LIMIT = get_settings().nearby_limit


def _distance(row) -> float | None:
    if row["latitude"] is None or row["longitude"] is None:
        return None
    return haversine_km(
        *REFERENCE_POINT, float(row["latitude"]), float(row["longitude"])
    )


def test_all_test_stores_carry_the_identifying_prefix():
    """契約無可標記的欄位，識別完全靠店名前綴（FR-035）。"""
    rows = _build_rows()

    assert rows
    assert all(row["name"].startswith(TEST_PREFIX) for row in rows)


def test_more_than_ten_stores_within_radius():
    """>10 家才驗得到「取最近 10 家」的截斷（FR-014）。"""
    within = [r for r in _build_rows() if (d := _distance(r)) is not None and d <= RADIUS_KM]

    assert len(within) > LIMIT


def test_has_stores_beyond_radius():
    """驗證半徑排除與「改看全部店家」（FR-019、FR-020）。"""
    beyond = [r for r in _build_rows() if (d := _distance(r)) is not None and d > RADIUS_KM]

    assert len(beyond) >= 1


def test_has_store_without_coordinates():
    """後台允許只建「名稱＋地址」——驗證 FR-018。"""
    no_coords = [r for r in _build_rows() if r["latitude"] is None]

    assert len(no_coords) >= 1
    # 座標必須成對缺少，不可只缺其一。
    assert all(r["longitude"] is None for r in no_coords)


def test_has_same_name_stores_at_different_addresses():
    """連鎖分店同名——驗證以 id 識別、以地址區分（FR-016a）。"""
    rows = _build_rows()
    by_name: dict[str, list] = {}
    for row in rows:
        by_name.setdefault(row["name"], []).append(row)

    duplicated = {name: rs for name, rs in by_name.items() if len(rs) > 1}
    assert duplicated, "缺少同名店家，FR-016a 無從驗證"

    for name, rs in duplicated.items():
        addresses = {r["address"] for r in rs}
        assert len(addresses) == len(rs), f"{name} 的同名分店必須有不同地址"
        ids = {_store_id(r["name"], r["address"]) for r in rs}
        assert len(ids) == len(rs), f"{name} 的同名分店必須有不同 id"


def test_distances_are_distinguishable_for_ordering():
    """相鄰店家的距離需有足夠差距，否則排序正確與否看不出來。"""
    within = sorted(
        d for r in _build_rows() if (d := _distance(r)) is not None and d <= RADIUS_KM
    )

    gaps = [b - a for a, b in zip(within, within[1:], strict=False)]
    assert all(gap > 0.05 for gap in gaps), "存在距離過近的店家，排序結果不易辨別"


def test_store_ids_are_deterministic_and_unique():
    """uuid5 推導鍵含地址——只用名稱會讓同名分店撞 id。"""
    rows = _build_rows()
    ids = [_store_id(r["name"], r["address"]) for r in rows]

    assert len(set(ids)) == len(rows)
    # 重複呼叫必須得到相同結果（upsert 的前提）。
    assert ids == [_store_id(r["name"], r["address"]) for r in rows]


def test_has_store_with_many_menu_items():
    """驗證清單捲動。"""
    counts = [len(_menu_for(r["name"])) for r in _build_rows()]

    assert max(counts) >= 8


def test_has_store_with_no_menu_items():
    """驗證餐點空狀態（FR-024）。"""
    counts = [len(_menu_for(r["name"])) for r in _build_rows()]

    assert 0 in counts


def test_has_menu_item_with_all_null_nutrition():
    """驗證「無資料」呈現（FR-025 前半）。"""
    all_items = [item for r in _build_rows() for item in _menu_for(r["name"])]
    all_null = [i for i in all_items if all(v is None for v in i[1:])]

    assert all_null, "缺少營養值全為 NULL 的餐點"


def test_has_menu_item_with_explicit_zero_nutrition():
    """驗證 0 顯示為 0 而非「無資料」（FR-025 後半）。

    這一筆是專門用來抓前端 falsy 誤判的——`value or '無資料'` 會把 0 顯示
    成「無資料」，而不會拋任何錯誤。少了這筆資料，那個 bug 驗不出來。
    """
    all_items = [item for r in _build_rows() for item in _menu_for(r["name"])]
    zeros = [i for i in all_items if any(v is not None and Decimal(v) == 0 for v in i[1:])]

    assert zeros, "缺少營養值為 0 的餐點，FR-025 後半無從驗證"


def test_has_duplicate_menu_item_names_within_one_store():
    """同店家內允許同名餐點，不得去重。"""
    for row in _build_rows():
        names = [i[0] for i in _menu_for(row["name"])]
        if len(names) != len(set(names)):
            return
    raise AssertionError("缺少同店同名的餐點，不去重的行為無從驗證")
