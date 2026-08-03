"""BMR／TDEE 與三大營養素目標公式（research.md R-13）。

以手算值比對——數值正確性無法靠人工檢視畫面驗證。
"""

from decimal import Decimal

import pytest

from app.services.targets import calculate_bmr, calculate_targets


def test_bmr_male_matches_mifflin_st_jeor():
    """10×68.5 + 6.25×175 − 5×28 + 5 = 685 + 1093.75 − 140 + 5 = 1643.75"""
    bmr = calculate_bmr("male", 28, Decimal("175"), Decimal("68.5"))
    assert bmr == Decimal("1643.75")


def test_bmr_female_applies_minus_161():
    """同樣身形的女性應比男性少 166 kcal（+5 與 −161 的差）。"""
    male = calculate_bmr("male", 28, Decimal("175"), Decimal("68.5"))
    female = calculate_bmr("female", 28, Decimal("175"), Decimal("68.5"))
    assert male - female == Decimal("166")
    assert female == Decimal("1477.75")


def test_tdee_applies_activity_multiplier():
    """中活動量係數 1.45：1643.75 × 1.45 = 2383.4375 → 2383.44"""
    targets = calculate_targets("male", 28, Decimal("175"), Decimal("68.5"), "moderate")
    assert targets.bmr_kcal == Decimal("1643.75")
    assert targets.tdee_kcal == Decimal("2383.44")


def test_activity_levels_are_ordered():
    args = ("male", 28, Decimal("175"), Decimal("68.5"))
    low = calculate_targets(*args, "low").tdee_kcal
    moderate = calculate_targets(*args, "moderate").tdee_kcal
    high = calculate_targets(*args, "high").tdee_kcal
    assert low < moderate < high


def test_protein_target_is_1_8g_per_kg():
    targets = calculate_targets("male", 28, Decimal("175"), Decimal("68.5"), "moderate")
    assert targets.protein_g == Decimal("123.3")  # 68.5 × 1.8


def test_fat_target_is_25_percent_of_calories():
    """2383.44 × 0.25 / 9 = 66.2066... → 66.2"""
    targets = calculate_targets("male", 28, Decimal("175"), Decimal("68.5"), "moderate")
    assert targets.fat_g == Decimal("66.2")


def test_carbs_target_is_remaining_calories():
    """(2383.44 − 123.3×4 − 66.2×9) / 4 = (2383.44 − 493.2 − 595.8)/4 = 323.61"""
    targets = calculate_targets("male", 28, Decimal("175"), Decimal("68.5"), "moderate")
    assert targets.carbs_g == Decimal("323.6")


def test_macro_calories_roughly_match_tdee():
    """三大營養素熱量總和應貼近 TDEE（僅四捨五入誤差）。"""
    targets = calculate_targets("female", 35, Decimal("162"), Decimal("55"), "low")
    macro_kcal = targets.protein_g * 4 + targets.carbs_g * 4 + targets.fat_g * 9
    assert abs(macro_kcal - targets.tdee_kcal) < Decimal("5")


def test_carbs_never_negative_for_extreme_body():
    """極端身形下碳水不得算成負數。"""
    targets = calculate_targets("male", 90, Decimal("140"), Decimal("300"), "low")
    assert targets.carbs_g >= Decimal("0")


def test_unknown_activity_level_raises():
    with pytest.raises(ValueError, match="未知的活動量等級"):
        calculate_targets("male", 28, Decimal("175"), Decimal("68.5"), "extreme")


def test_recalculation_changes_targets_when_weight_changes():
    """FR-015：修改體重後目標值必須改變。"""
    before = calculate_targets("male", 28, Decimal("175"), Decimal("68.5"), "moderate")
    after = calculate_targets("male", 28, Decimal("175"), Decimal("75.0"), "moderate")
    assert after.tdee_kcal > before.tdee_kcal
    assert after.protein_g > before.protein_g
