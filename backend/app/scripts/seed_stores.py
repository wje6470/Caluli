"""載入推薦餐廳模組的測試店家／餐點（第二輪）。

⚠️ 為什麼是 seed script 而不是 migration（research.md R-09）
==============================================================
migration 會在每個環境自動執行，假店家將自動進入正式資料庫。而共用契約
沒有 is_test 之類的欄位可供區分，本輪又不得增減欄位——一旦第三輪的後台
寫入正式資料，兩者混在同一張表卻無從分辨，清理成本極高。

seed script 需要有人主動執行，環境邊界清楚。

識別方式
========
契約無可標記的欄位，故以**店名前綴 `[測試]`** 標示（spec FR-035）。前綴會
顯示在畫面上，這是刻意的：測試環境一眼可辨，且正式資料寫入後兩者並存也
不會被誤認。清除時以 `name LIKE '[測試]%'` 即可精準刪除。

主鍵推導
========
以 uuid5 從固定命名空間推導，使重複執行為 upsert 而非重複插入，且測試可
直接以已知 UUID 斷言。

⚠️ 推導鍵**不可只用名稱**——2026-08-04 交接確認店名不具唯一性（連鎖分店
同名），故店家用 f"{name}|{address}"、餐點用 f"{store_id}|{index}|{name}"。
這是 seed 內部的識別方式，**不是**對資料表的唯一性假設；正式資料的識別
一律靠 id。

用法
====
    python -m app.scripts.seed_stores            # 載入／更新
    python -m app.scripts.seed_stores --purge    # 清除全部測試資料
"""

import argparse
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.db.models import MenuItem, Store
from app.db.session import SessionLocal

#: 測試資料的識別前綴（FR-035）。
TEST_PREFIX = "[測試]"

#: 固定的 uuid5 命名空間，使 seed 可重複執行且主鍵穩定。
SEED_NAMESPACE = uuid.UUID("6f1b2c8e-0000-5000-8000-000000000000")

#: quickstart.md 的驗證參考點：台北車站。
REFERENCE_POINT = (25.0478, 121.5170)


def _store_id(name: str, address: str | None) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{name}|{address or ''}")


def _menu_item_id(store_id: uuid.UUID, index: int, name: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{store_id}|{index}|{name}")


def _d(value: str | None) -> Decimal | None:
    """None 保持 None——營養值的 NULL 與 0 是兩種不同的狀態（FR-025）。"""
    return None if value is None else Decimal(value)


# =============================================================================
# 測試資料
#
# 每一組都對應一個驗收情境，缺一項就有情境驗不到（tasks.md T009）。
# 座標以台北車站為基準向北偏移，0.001 緯度約 111 公尺。
# =============================================================================

# --- 台北車站 5 公里內，共 12 家（>10 才驗得到「取最近 10 家」的截斷）---
_NEARBY = [
    # (名稱, 地址, 緯度偏移) — 依距離由近至遠
    ("台北車站便當屋", "臺北市中正區忠孝西路一段 49 號", 0.0005),
    ("站前輕食坊", "臺北市中正區館前路 12 號", 0.0020),
    ("南陽街咖哩", "臺北市中正區南陽街 20 號", 0.0040),
    ("開封街麵舖", "臺北市中正區開封街一段 33 號", 0.0070),
    ("北門鹹粥", "臺北市大同區延平南路 8 號", 0.0100),
    ("中山溫體牛", "臺北市中山區南京西路 5 號", 0.0140),
    ("赤峰街素食", "臺北市大同區赤峰街 41 號", 0.0180),
    ("雙連蔬食堂", "臺北市大同區民生西路 100 號", 0.0230),
    ("民權西路雞湯", "臺北市大同區民權西路 66 號", 0.0280),
    ("圓山健康廚房", "臺北市中山區玉門街 1 號", 0.0340),
]

# --- 同名不同址的連鎖分店（驗證 FR-016a：以 id 識別、以地址區分、不去重）---
_CHAIN_NAME = "連鎖健康餐盒"
_CHAIN = [
    ("臺北市中正區公園路 30 號", 0.0390),
    ("臺北市大同區承德路二段 55 號", 0.0430),
]

# --- 5 公里外（驗證半徑排除與「改看全部店家」，FR-019／FR-020）---
_FAR = [
    ("淡水河岸食堂", "新北市淡水區中正路 11 號", 25.1677, 121.4406),
    ("基隆廟口海鮮", "基隆市仁愛區仁三路 27 號", 25.1276, 121.7392),
]

# --- 無座標（後台允許只建名稱＋地址；驗證 FR-018）---
_NO_COORDS = ("尚未定位的新店家", "臺北市信義區市府路 45 號")


def _menu_for(store_name: str) -> list[tuple[str, str | None, str | None, str | None, str | None]]:
    """回傳 (餐點名, calories, protein_g, carbs_g, fat_g)，None 代表店家未提供。"""

    # 第一家：8 筆以上（驗證捲動），並涵蓋三種關鍵資料形態。
    if store_name == f"{TEST_PREFIX} 台北車站便當屋":
        return [
            ("排骨便當", "780", "28.50", "95.00", "30.20"),
            ("雞腿便當", "820", "32.00", "94.50", "33.10"),
            ("鱈魚便當", "690", "30.20", "88.00", "22.40"),
            ("素食便當", "610", "18.00", "92.00", "18.60"),
            # 同店同名的兩筆餐點——驗證不去重（FR-016a）。
            ("招牌便當", "750", "27.00", "90.00", "29.00"),
            ("招牌便當", "880", "34.00", "98.00", "36.50"),
            # 四欄皆 NULL：店家未提供 → 畫面必須顯示「無資料」（FR-025 前半）。
            ("季節時蔬", None, None, None, None),
            # 營養值確實為 0：→ 畫面必須顯示 0，不得顯示「無資料」（FR-025 後半）。
            # 這一筆存在的唯一理由就是抓前端的 falsy 誤判。
            ("無糖清茶", "0", "0.00", "0.00", "0.00"),
        ]

    # 第二家：0 筆餐點（驗證空狀態，FR-024）。
    if store_name == f"{TEST_PREFIX} 站前輕食坊":
        return []

    # 其餘店家：各 3 筆一般資料。
    return [
        ("招牌套餐", "650", "25.00", "80.00", "24.00"),
        ("輕食沙拉", "320", "12.50", "35.00", "14.20"),
        ("每日湯品", "180", "8.00", "20.00", "6.50"),
    ]


def _build_rows() -> list[dict]:
    """組出全部測試店家（含其餐點）。"""
    rows: list[dict] = []
    base_lat, base_lng = REFERENCE_POINT

    for name, address, lat_offset in _NEARBY:
        rows.append(
            {
                "name": f"{TEST_PREFIX} {name}",
                "address": address,
                "latitude": Decimal(str(round(base_lat + lat_offset, 6))),
                "longitude": Decimal(str(base_lng)),
            }
        )

    for address, lat_offset in _CHAIN:
        rows.append(
            {
                "name": f"{TEST_PREFIX} {_CHAIN_NAME}",
                "address": address,
                "latitude": Decimal(str(round(base_lat + lat_offset, 6))),
                "longitude": Decimal(str(base_lng)),
            }
        )

    for name, address, lat, lng in _FAR:
        rows.append(
            {
                "name": f"{TEST_PREFIX} {name}",
                "address": address,
                "latitude": Decimal(str(lat)),
                "longitude": Decimal(str(lng)),
            }
        )

    name, address = _NO_COORDS
    rows.append(
        {
            "name": f"{TEST_PREFIX} {name}",
            "address": address,
            "latitude": None,
            "longitude": None,
        }
    )

    return rows


def seed() -> tuple[int, int]:
    """載入或更新測試資料。回傳 (店家數, 餐點數)。"""
    rows = _build_rows()
    store_count = item_count = 0

    with SessionLocal() as db:
        for row in rows:
            store_id = _store_id(row["name"], row["address"])
            store = db.get(Store, store_id)
            if store is None:
                store = Store(id=store_id, **row)
                db.add(store)
            else:
                for key, value in row.items():
                    setattr(store, key, value)
            store_count += 1

            # 餐點同樣以決定性 id upsert；本次不再出現的舊餐點一併刪除，
            # 避免調整 seed 內容後殘留孤兒資料。
            desired = _menu_for(row["name"])
            keep: set[uuid.UUID] = set()
            for index, (item_name, cal, pro, carb, fat) in enumerate(desired):
                item_id = _menu_item_id(store_id, index, item_name)
                keep.add(item_id)
                values = {
                    "store_id": store_id,
                    "name": item_name,
                    "calories": _d(cal),
                    "protein_g": _d(pro),
                    "carbs_g": _d(carb),
                    "fat_g": _d(fat),
                }
                item = db.get(MenuItem, item_id)
                if item is None:
                    db.add(MenuItem(id=item_id, **values))
                else:
                    for key, value in values.items():
                        setattr(item, key, value)
                item_count += 1

            existing_items = db.scalars(
                select(MenuItem).where(MenuItem.store_id == store_id)
            ).all()
            for item in existing_items:
                if item.id not in keep:
                    db.delete(item)

        db.commit()

    return store_count, item_count


def purge() -> int:
    """刪除全部測試店家（餐點由 ON DELETE CASCADE 連帶刪除）。回傳刪除筆數。

    以 name 前綴精準匹配，正式資料不受影響。
    """
    with SessionLocal() as db:
        stores = db.scalars(select(Store).where(Store.name.like(f"{TEST_PREFIX}%"))).all()
        for store in stores:
            db.delete(store)
        db.commit()
        return len(stores)


def main() -> int:
    parser = argparse.ArgumentParser(description="載入推薦餐廳模組的測試店家／餐點")
    parser.add_argument(
        "--purge",
        action="store_true",
        help=f"刪除全部以 {TEST_PREFIX} 為前綴的測試店家（含其餐點）",
    )
    args = parser.parse_args()

    if args.purge:
        removed = purge()
        print(f"已刪除 {removed} 家測試店家（餐點由 CASCADE 連帶刪除）")
        return 0

    stores, items = seed()
    print(f"已載入／更新 {stores} 家測試店家、{items} 筆餐點")
    print(f"驗證參考點：台北車站 {REFERENCE_POINT}（DevTools → Sensors → Location）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
