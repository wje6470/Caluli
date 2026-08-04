"""距離計算（推薦餐廳模組，第二輪）。

research.md R-01 — 為什麼在應用層算，而不是寫進 SQL
=====================================================
brief 已排除 PostGIS，剩下的選擇是「應用層迴圈」與「SQL 內嵌 Haversine」。
本專案選應用層，決定性理由是**可測試性**：

  haversine_km() 是純函式，不碰 Session、不碰 ORM，因此能在沒有資料庫的
  環境下驗證已知距離、同點為零、經度換日線與極值座標。而距離排序的正確性
  正是本輪最核心的可測邏輯（spec SC-002）。

  SQL 內嵌版本需以 sa.func.acos(sa.func.sin(...)) 層層包裝，既難讀又必須
  起資料庫才驗得到——若在本檔引入任何 Session 依賴，等於放棄該決策的全部
  收益，請勿這麼做。

應用層的代價是每次查詢取回全表，但在「店家數量不大」的前提下不成問題
（數十筆的計算耗時遠低於一次網路往返）。

成長觸發點（先寫下來，避免日後憑感覺改架構）：店家數約 1,000 筆前無需
處理；超過後的升級順序是 (1) 先在 SQL 加經緯度 bounding box 粗篩再於應用層
精算，(2) 仍不足才評估 PostGIS。**本輪不實作 (1)**，因為那會讓半徑邏輯
同時存在於 SQL 與 Python 兩處。
"""

import math

#: IUGG 平均地球半徑（公里）。
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """兩點間的大圓（直線）距離，單位公里。

    注意這是直線距離，不是道路或步行距離——實際步行距離在都會區約為此值
    的 1.3〜1.5 倍。spec 的 5 公里半徑上限亦以直線距離認定。

    經度換日線（±180）不需特別處理：Haversine 取的是經度差的正弦平方，
    Δλ 為 +350° 或 -10° 得到的結果相同。
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    # 浮點誤差可能讓 a 微幅超過 1（同點或極近距離時），asin 會因此 domain
    # error。夾在 [0, 1] 內是必要的防護，不是保守寫法。
    a = min(1.0, max(0.0, a))

    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
