"""匯入通用食物營養對照表。

⚠️ OQ-2（未定案）：資料來源與涵蓋範圍尚未確認。本腳本以「可替換的 CSV」
為輸入，並附一份最小種子資料供開發與驗證使用。正式資料就緒後，只需替換
CSV 檔即可，不需改動程式碼。

CSV 欄位（含表頭）：
    model_label,name,calories_kcal_per_100g,protein_g_per_100g,
    carbs_g_per_100g,fat_g_per_100g,default_portion_grams,source

**每個可辨識的模型類別都必須在此表中有對應列**；缺漏的類別在辨識時會
落入 nutrition_available=false 路徑（FR-037），使用者需自行填入數值。
"""

import csv
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.models import FoodNutritionReference, normalize_food_name
from app.db.session import SessionLocal

DEFAULT_CSV = Path(__file__).parent / "data" / "food_nutrition_seed.csv"


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def seed(csv_path: Path = DEFAULT_CSV) -> tuple[int, int]:
    """匯入或更新對照表。回傳 (新增數, 更新數)。"""
    rows = load_rows(csv_path)
    created = updated = 0

    with SessionLocal() as db:
        for row in rows:
            label = row["model_label"].strip()
            existing = db.scalar(
                select(FoodNutritionReference).where(FoodNutritionReference.model_label == label)
            )
            values = {
                "name": row["name"].strip(),
                "name_normalized": normalize_food_name(row["name"]),
                "calories_kcal_per_100g": Decimal(row["calories_kcal_per_100g"]),
                "protein_g_per_100g": Decimal(row["protein_g_per_100g"]),
                "carbs_g_per_100g": Decimal(row["carbs_g_per_100g"]),
                "fat_g_per_100g": Decimal(row["fat_g_per_100g"]),
                "default_portion_grams": Decimal(row["default_portion_grams"]),
                "source": (row.get("source") or "").strip() or None,
            }

            if existing is None:
                db.add(FoodNutritionReference(model_label=label, **values))
                created += 1
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
                updated += 1

        db.commit()

    return created, updated


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path.is_file():
        print(f"找不到種子資料檔：{csv_path}", file=sys.stderr)
        return 1

    created, updated = seed(csv_path)
    print(f"通用食物營養對照表匯入完成：新增 {created} 筆、更新 {updated} 筆")
    print("⚠️ OQ-2 未定案——請確認此資料是否涵蓋辨識模型的所有輸出類別。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
