"""憲章原則 V — 兩套營養資料表分離的靜態稽核（tasks.md T051）。

「拍照辨識用之通用食物營養對照表」(food_nutrition_references) 與「特定
店家／餐點之營養值」(menu_items) 是兩套完全獨立的資料。兩者之間禁止建立
任何方向的外鍵、禁止合併、禁止以型別欄位混存（spec FR-030、FR-031）。

這裡做的是**靜態**稽核——檢查模型關聯與 import 關係。行為面的驗證
（修改一方的數值不影響另一方的呈現）在 integration 測試中進行，需要資料庫。

靜態稽核的價值在於它在任何環境都跑得到，且能在關聯被加上的當下就失敗，
而不是等到有人發現數值互相汙染。
"""

import ast
from pathlib import Path

from app.db.models import FoodNutritionReference, MenuItem, Store

BACKEND_ROOT = Path(__file__).resolve().parents[2]

#: 第一輪通用食物營養對照表體系的模組，本輪的店家查詢不得依賴。
ROUND1_NUTRITION_MODULES = {
    "app.db.models.food_reference",
    "app.services.nutrition",
    "app.services.recognition_client",
}


def _foreign_key_targets(model) -> set[str]:
    targets = set()
    for column in model.__table__.columns:
        for fk in column.foreign_keys:
            targets.add(fk.target_fullname.split(".")[0])
    return targets


def test_menu_items_has_no_foreign_key_to_food_reference():
    """menu_items 的外鍵只能指向 stores。"""
    targets = _foreign_key_targets(MenuItem)

    assert targets == {"stores"}, f"menu_items 不應有指向 {targets - {'stores'}} 的外鍵"
    assert FoodNutritionReference.__tablename__ not in targets


def test_stores_has_no_foreign_keys_at_all():
    assert _foreign_key_targets(Store) == set()


def test_food_reference_has_no_foreign_key_to_store_tables():
    """反向也不允許——第一輪的表不得指向本輪的表。"""
    targets = _foreign_key_targets(FoodNutritionReference)

    assert "stores" not in targets
    assert "menu_items" not in targets


def test_two_nutrition_datasets_are_separate_tables():
    """不得合併為同一張表。"""
    assert MenuItem.__tablename__ != FoodNutritionReference.__tablename__
    assert MenuItem.__tablename__ == "menu_items"
    assert FoodNutritionReference.__tablename__ == "food_nutrition_references"


def test_no_shared_columns_implying_mixed_storage():
    """本輪的表不得帶有 model_label 之類屬於辨識體系的欄位。"""
    menu_columns = {c.name for c in MenuItem.__table__.columns}

    assert "model_label" not in menu_columns
    assert "default_portion_grams" not in menu_columns
    # 也不得以型別欄位在單表內混存兩類資料。
    assert "type" not in menu_columns
    assert "category" not in menu_columns


def test_stores_service_does_not_import_round1_nutrition_modules():
    """app/services/stores.py 不得依賴第一輪的營養模組。

    以 AST 解析 import 語句——比字串搜尋精確，不會被註解或字面值誤導
    （本輪的原始碼註解中就提到了這些模組名）。
    """
    source = (BACKEND_ROOT / "app" / "services" / "stores.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)

    leaked = imported & ROUND1_NUTRITION_MODULES
    assert leaked == set(), (
        f"店家查詢不得依賴第一輪的通用食物營養對照表體系（憲章原則 V），"
        f"但發現 import：{leaked}"
    )
    assert "FoodNutritionReference" not in {n.split(".")[-1] for n in imported}
