"""營養換算與驗算容忍值（FR-023、research.md R-09）。"""

from decimal import Decimal

from app.services.nutrition import (
    Nutrients,
    scale,
    sum_all,
    verify_and_correct,
    within_tolerance,
)

# 滷肉飯每 100g（種子資料）
BRAISED_PORK_RICE = Nutrients(
    calories_kcal=Decimal("187.00"),
    protein_g=Decimal("6.20"),
    carbs_g=Decimal("26.10"),
    fat_g=Decimal("6.50"),
)


def test_scale_at_default_portion():
    """預設份量 250g：187 × 250/100 = 467.5 kcal。"""
    result = scale(BRAISED_PORK_RICE, Decimal("250"))
    assert result.calories_kcal == Decimal("467.50")
    assert result.protein_g == Decimal("15.50")
    assert result.carbs_g == Decimal("65.25")
    assert result.fat_g == Decimal("16.25")


def test_scale_after_user_adjustment():
    """使用者調整為 375g（quickstart V3 的驗證數值）。"""
    result = scale(BRAISED_PORK_RICE, Decimal("375"))
    assert result.calories_kcal == Decimal("701.25")
    assert result.protein_g == Decimal("23.25")


def test_scale_at_exactly_100g_returns_per_100g_values():
    result = scale(BRAISED_PORK_RICE, Decimal("100"))
    assert result.calories_kcal == Decimal("187.00")


def test_within_tolerance_accepts_display_rounding():
    """前端顯示四捨五入造成的正常差異應被接受。"""
    assert within_tolerance(Decimal("467.50"), Decimal("467.5"))
    assert within_tolerance(Decimal("467.50"), Decimal("468"))


def test_within_tolerance_rejects_tampering():
    assert not within_tolerance(Decimal("467.50"), Decimal("100.00"))


def test_verify_uses_backend_value_when_client_tampers():
    """客戶端數值不採信——差異過大時以後端計算值為準。"""
    tampered = Nutrients(
        calories_kcal=Decimal("50.00"),
        protein_g=Decimal("1.00"),
        carbs_g=Decimal("1.00"),
        fat_g=Decimal("1.00"),
    )
    authoritative, corrected = verify_and_correct(BRAISED_PORK_RICE, Decimal("250"), tampered)
    assert corrected is True
    assert authoritative.calories_kcal == Decimal("467.50")


def test_verify_accepts_matching_client_value():
    claimed = scale(BRAISED_PORK_RICE, Decimal("250"))
    authoritative, corrected = verify_and_correct(BRAISED_PORK_RICE, Decimal("250"), claimed)
    assert corrected is False
    assert authoritative == claimed


def test_verify_without_client_value_computes_from_scratch():
    authoritative, corrected = verify_and_correct(BRAISED_PORK_RICE, Decimal("250"), None)
    assert corrected is False
    assert authoritative.calories_kcal == Decimal("467.50")


def test_sum_all_totals_multiple_items():
    a = scale(BRAISED_PORK_RICE, Decimal("100"))
    b = scale(BRAISED_PORK_RICE, Decimal("200"))
    total = sum_all([a, b])
    assert total.calories_kcal == Decimal("561.00")


def test_sum_all_empty_is_zero():
    assert sum_all([]).calories_kcal == Decimal("0")
