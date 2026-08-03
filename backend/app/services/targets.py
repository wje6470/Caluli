"""BMR／TDEE 與三大營養素目標計算（research.md R-13）。

計算集中於後端單一函式：TDEE 會寫入資料表並影響儀表板與趨勢的達成率，
若前後端各算一次，浮點與四捨五入差異會造成畫面與資料庫不一致。
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

#: 活動量係數（與 prototype 一致）。
ACTIVITY_MULTIPLIERS: dict[str, Decimal] = {
    "low": Decimal("1.2"),
    "moderate": Decimal("1.45"),
    "high": Decimal("1.75"),
}

PROTEIN_G_PER_KG = Decimal("1.8")
FAT_CALORIE_RATIO = Decimal("0.25")

KCAL_PER_G_PROTEIN = Decimal("4")
KCAL_PER_G_CARBS = Decimal("4")
KCAL_PER_G_FAT = Decimal("9")


@dataclass(frozen=True)
class DailyTargets:
    bmr_kcal: Decimal
    tdee_kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


def _round(value: Decimal, places: str = "0.1") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def calculate_bmr(gender: str, age_years: int, height_cm: Decimal, weight_kg: Decimal) -> Decimal:
    """Mifflin-St Jeor 公式。

    BMR = 10×體重kg + 6.25×身高cm − 5×年齡 + (男 +5 / 女 −161)
    """
    base = (
        Decimal("10") * Decimal(weight_kg)
        + Decimal("6.25") * Decimal(height_cm)
        - Decimal("5") * Decimal(age_years)
    )
    adjustment = Decimal("5") if gender == "male" else Decimal("-161")
    return _round(base + adjustment, "0.01")


def calculate_targets(
    gender: str, age_years: int, height_cm: Decimal, weight_kg: Decimal, activity_level: str
) -> DailyTargets:
    bmr = calculate_bmr(gender, age_years, height_cm, weight_kg)

    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level)
    if multiplier is None:
        raise ValueError(f"未知的活動量等級：{activity_level}")

    tdee = _round(bmr * multiplier, "0.01")

    protein_g = _round(Decimal(weight_kg) * PROTEIN_G_PER_KG)
    fat_g = _round(tdee * FAT_CALORIE_RATIO / KCAL_PER_G_FAT)
    carbs_kcal = tdee - (protein_g * KCAL_PER_G_PROTEIN) - (fat_g * KCAL_PER_G_FAT)
    # 極端身形下碳水可能算成負數，夾到 0 以免產生無意義的目標值。
    carbs_g = _round(max(carbs_kcal, Decimal("0")) / KCAL_PER_G_CARBS)

    return DailyTargets(
        bmr_kcal=bmr,
        tdee_kcal=tdee,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
    )
