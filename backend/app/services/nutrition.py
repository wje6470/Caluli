"""營養換算與驗算（research.md R-09）。

換算公式：value = per_100g × grams / 100

前端在辨識確認畫面即時執行同一公式（不呼叫後端），後端在**儲存時重新
驗算**——客戶端送來的數值不可信，且能防止四捨五入誤差累積進歷史資料。
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

HUNDRED = Decimal("100")

#: 驗算容忍值：絕對 0.5 或相對 1%，取較大者。
#: 容忍前端浮點運算與顯示四捨五入的正常差異，但擋掉刻意竄改。
ABS_TOLERANCE = Decimal("0.5")
REL_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class Nutrients:
    calories_kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal

    def __add__(self, other: "Nutrients") -> "Nutrients":
        return Nutrients(
            calories_kcal=self.calories_kcal + other.calories_kcal,
            protein_g=self.protein_g + other.protein_g,
            carbs_g=self.carbs_g + other.carbs_g,
            fat_g=self.fat_g + other.fat_g,
        )

    @classmethod
    def zero(cls) -> "Nutrients":
        z = Decimal("0")
        return cls(z, z, z, z)


def _round(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def scale(per_100g: Nutrients, grams: Decimal) -> Nutrients:
    """依份量換算營養值。熱量取兩位小數保存，顯示層再取整。"""
    factor = Decimal(grams) / HUNDRED
    return Nutrients(
        calories_kcal=_round(per_100g.calories_kcal * factor, "0.01"),
        protein_g=_round(per_100g.protein_g * factor, "0.01"),
        carbs_g=_round(per_100g.carbs_g * factor, "0.01"),
        fat_g=_round(per_100g.fat_g * factor, "0.01"),
    )


def within_tolerance(expected: Decimal, actual: Decimal) -> bool:
    tolerance = max(ABS_TOLERANCE, abs(expected) * REL_TOLERANCE)
    return abs(expected - actual) <= tolerance


def verify_and_correct(
    per_100g: Nutrients, grams: Decimal, claimed: Nutrients | None
) -> tuple[Nutrients, bool]:
    """驗算客戶端送來的數值。

    回傳 (權威數值, 是否曾修正)。差異超過容忍值即以後端計算值為準——
    客戶端數值不採信，避免竄改污染趨勢統計的可信度。
    """
    expected = scale(per_100g, grams)
    if claimed is None:
        return expected, False

    fields = ("calories_kcal", "protein_g", "carbs_g", "fat_g")
    corrected = any(not within_tolerance(getattr(expected, f), getattr(claimed, f)) for f in fields)
    return expected, corrected


def sum_all(items: list[Nutrients]) -> Nutrients:
    total = Nutrients.zero()
    for item in items:
        total = total + item
    return total
