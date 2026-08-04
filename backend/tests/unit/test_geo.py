"""距離公式的單元測試（tasks.md T012）。

刻意不依賴資料庫——這正是 research.md R-01 選擇應用層計算的理由。
若哪天這支測試需要 db fixture 才能跑，代表 geo.py 被汙染了。
"""

import math

import pytest

from app.services.geo import EARTH_RADIUS_KM, haversine_km

# 驗證用的參考座標。
TAIPEI_MAIN_STATION = (25.0478, 121.5170)
TAMSUI = (25.1677, 121.4406)
KAOHSIUNG = (22.6273, 120.3014)


def test_same_point_is_zero():
    """同一點距離為 0——浮點誤差不得讓 asin 拋 domain error。"""
    lat, lng = TAIPEI_MAIN_STATION
    assert haversine_km(lat, lng, lat, lng) == pytest.approx(0.0, abs=1e-9)


def test_known_distance_taipei_to_tamsui():
    """台北車站↔淡水約 15 公里（直線）。

    容許 ±1.5 km 誤差：不同來源的參考座標本身就有差異，此測試要抓的是
    量級錯誤（單位寫成公尺、半徑取錯、經緯度顛倒），不是小數點後的精度。
    """
    d = haversine_km(*TAIPEI_MAIN_STATION, *TAMSUI)
    assert d == pytest.approx(15.0, abs=1.5)


def test_known_distance_taipei_to_kaohsiung():
    """台北↔高雄約 297 公里——用來確認長距離不失真。"""
    d = haversine_km(*TAIPEI_MAIN_STATION, *KAOHSIUNG)
    assert d == pytest.approx(297.0, abs=10.0)


def test_latitude_and_longitude_not_swapped():
    """經緯度顛倒會得到明顯不同的結果——這是最常見的低級錯誤。"""
    correct = haversine_km(*TAIPEI_MAIN_STATION, *TAMSUI)
    swapped = haversine_km(
        TAIPEI_MAIN_STATION[1], TAIPEI_MAIN_STATION[0], TAMSUI[1], TAMSUI[0]
    )
    assert not math.isclose(correct, swapped, rel_tol=0.1)


def test_antimeridian_does_not_produce_absurd_distance():
    """跨經度換日線（±180）不得算出繞地球一圈的距離。

    179.9°E 與 179.9°W 實際相距約 22 公里，若公式處理不當會得到約
    40,000 公里（繞行整圈）。
    """
    d = haversine_km(0.0, 179.9, 0.0, -179.9)
    assert d < 50.0


def test_poles_do_not_raise():
    """極值座標不得拋例外。"""
    assert haversine_km(90.0, 0.0, -90.0, 0.0) == pytest.approx(
        math.pi * EARTH_RADIUS_KM, rel=1e-6
    )
    assert haversine_km(-90.0, 180.0, 90.0, -180.0) > 0


def test_symmetry():
    """距離對稱：A→B 與 B→A 相等。"""
    forward = haversine_km(*TAIPEI_MAIN_STATION, *TAMSUI)
    backward = haversine_km(*TAMSUI, *TAIPEI_MAIN_STATION)
    assert forward == pytest.approx(backward, rel=1e-12)


def test_short_distance_precision():
    """約 100 公尺的短距離仍應有意義的解析度（不得因夾值而歸零）。"""
    lat, lng = TAIPEI_MAIN_STATION
    d = haversine_km(lat, lng, lat + 0.0009, lng)  # 約 100 公尺
    assert 0.05 < d < 0.15
