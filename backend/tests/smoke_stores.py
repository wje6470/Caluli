"""推薦餐廳的真實 HTTP 冒煙測試（第二輪，tasks.md T055／T056 的自動化部分）。

對**實際運行中**的服務執行，涵蓋 quickstart.md 的 V1〜V3、V7、V8、V10、V12
之後端路徑，並量測回應時間（SC-007）。

與 pytest 整合測試的差別：那些走 ASGITransport 且在交易中 rollback；這裡是
真的 HTTP、真的 uvicorn 堆疊、真的資料庫查詢——涵蓋 TestClient 驗不到的
路由前綴、序列化（Decimal → JSON）與相依注入行為。

用法：
    uv run python tests/smoke_stores.py
需先啟動 API（:8000）與 PostgreSQL，並已執行 seed_stores.py。
"""

import sys
import time
import uuid

import httpx

from app.core.security import create_access_token
from app.db.models import User
from app.db.session import SessionLocal

API = "http://127.0.0.1:8000/api/v1"

TAIPEI = (25.0478, 121.5170)
TAMSUI = (25.1677, 121.4406)
KAOHSIUNG = (22.6273, 120.3014)

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{f' — {detail}' if detail else ''}")


def make_user() -> tuple[str, uuid.UUID]:
    with SessionLocal() as db:
        user = User(line_user_id=f"Usmoke{uuid.uuid4().hex}", display_name="冒煙測試")
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(user.id)
        return token, user.id


def drop_user(user_id: uuid.UUID) -> None:
    """清掉冒煙測試建立的使用者。

    ⚠️ 必須清理：第一輪的 tests/integration/test_auth.py 以**絕對總數**斷言
    （`db_session.query(User).count() == 1`），任何殘留的已提交使用者都會讓
    那三支測試失敗。本檔的殘留曾實際造成這個問題。
    """
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is not None:
            db.delete(user)
            db.commit()


def run_checks(c: httpx.Client, auth: dict[str, str]) -> int:
    # --- V12：未登入被拒（FR-004）---
    print("\n[V12] 驗證與授權")
    r = c.get(f"{API}/stores")
    check("未帶 token 回 401", r.status_code == 401, f"實際 {r.status_code}")

    # --- V1：附近模式（FR-014、FR-016、SC-002、SC-007）---
    print("\n[V1] 附近店家清單")
    t0 = time.perf_counter()
    r = c.get(f"{API}/stores", params={"lat": TAIPEI[0], "lng": TAIPEI[1]}, headers=auth)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    body = r.json()

    check("回應 200", r.status_code == 200, f"實際 {r.status_code}")
    check("mode=nearby", body["mode"] == "nearby")
    check("radius_km=5", body["radius_km"] == 5.0)
    check("筆數 <= 10", len(body["stores"]) <= 10, f"{len(body['stores'])} 筆")
    dists = [s["distance_m"] for s in body["stores"]]
    check("距離升冪排序", dists == sorted(dists), f"{dists}")
    check("全部在 5 公里內", all(d <= 5000 for d in dists))
    check("每筆都有店名與地址", all(s["name"] and s["address"] for s in body["stores"]))
    check("無座標店家不在清單中", all("尚未定位" not in s["name"] for s in body["stores"]))
    check("SC-007 清單回應 < 2000ms", elapsed_ms < 2000, f"{elapsed_ms:.0f} ms")

    # --- V2：半徑排除，不以範圍外店家補足（FR-020）---
    print("\n[V2] 半徑邊界")
    r = c.get(f"{API}/stores", params={"lat": TAMSUI[0], "lng": TAMSUI[1]}, headers=auth)
    tam = r.json()["stores"]
    check("淡水只回範圍內的店家", len(tam) == 1, f"{len(tam)} 筆：{[s['name'] for s in tam]}")
    check("未以台北的店家補足至 10 筆", len(tam) < 10)

    # --- V3：兩種空狀態可區分（FR-019、R-05）---
    print("\n[V3] 空狀態")
    r = c.get(f"{API}/stores", params={"lat": KAOHSIUNG[0], "lng": KAOHSIUNG[1]}, headers=auth)
    kh = r.json()
    check("高雄附近查無店家", kh["stores"] == [], f"{len(kh['stores'])} 筆")
    check(
        "total_store_count > 0（前端據此提供『改看全部店家』）",
        kh["total_store_count"] > 0,
        f"total={kh['total_store_count']}",
    )

    # --- 全部模式（FR-017、FR-018）---
    print("\n[V4] 全部模式（定位被拒／失敗的替代路徑）")
    r = c.get(f"{API}/stores", headers=auth)
    allb = r.json()
    check("mode=all", allb["mode"] == "all")
    check("radius_km=null", allb["radius_km"] is None)
    check("距離皆為 null", all(s["distance_m"] is None for s in allb["stores"]))
    check(
        "無座標店家出現在全部清單中",
        any("尚未定位" in s["name"] for s in allb["stores"]),
    )

    # --- 座標驗證（R-06、R-07）---
    print("\n[驗證] 座標參數")
    r = c.get(f"{API}/stores", params={"lat": TAIPEI[0]}, headers=auth)
    check("只給 lat 回 422（不無聲退回全部模式）", r.status_code == 422, f"實際 {r.status_code}")
    r = c.get(f"{API}/stores", params={"lat": 999, "lng": 0}, headers=auth)
    check("超出範圍的座標回 422", r.status_code == 422, f"實際 {r.status_code}")

    # --- V7：餐點與 null/0 區分（FR-023、FR-025）---
    print("\n[V7] 餐點營養：null 與 0 的區分")
    bento = next(s for s in allb["stores"] if "便當屋" in s["name"])
    t0 = time.perf_counter()
    r = c.get(f"{API}/stores/{bento['id']}/menu-items", headers=auth)
    menu_ms = (time.perf_counter() - t0) * 1000
    items = r.json()["menu_items"]

    check("回應 200", r.status_code == 200)
    check("餐點筆數 >= 8（可捲動）", len(items) >= 8, f"{len(items)} 筆")
    nulls = [i for i in items if i["calories_kcal"] is None]
    zeros = [i for i in items if i["calories_kcal"] is not None and float(i["calories_kcal"]) == 0]
    check(
        "有 null 營養值的餐點（顯示「無資料」）",
        len(nulls) == 1,
        f"{[i['name'] for i in nulls]}",
    )
    check("有 0 營養值的餐點（顯示 0）", len(zeros) == 1, f"{[i['name'] for i in zeros]}")
    check(
        "★ null 未被序列化為 0",
        all(i["protein_g"] is None for i in nulls),
        "JSON 中確實為 null",
    )
    check(
        "★ 0 未被序列化為 null",
        all(i["protein_g"] is not None for i in zeros),
        "JSON 中確實為 0",
    )
    names = [i["name"] for i in items]
    check("同名餐點未去重", len(names) != len(set(names)))
    check("SC-007 餐點載入 < 2000ms", menu_ms < 2000, f"{menu_ms:.0f} ms")

    # --- V8：無餐點的店家（FR-024）---
    print("\n[V8] 店家無餐點")
    light = next(s for s in allb["stores"] if "輕食坊" in s["name"])
    r = c.get(f"{API}/stores/{light['id']}/menu-items", headers=auth)
    check("回 200 而非 404（空清單是正常結果）", r.status_code == 200, f"實際 {r.status_code}")
    check("menu_items 為空陣列", r.json()["menu_items"] == [])

    # --- V12：不存在的店家（FR-027）---
    print("\n[V12] 不存在的店家")
    r = c.get(f"{API}/stores/{uuid.uuid4()}", headers=auth)
    check("回 404", r.status_code == 404, f"實際 {r.status_code}")
    check("錯誤信封格式正確", r.json().get("error", {}).get("code") == "NOT_FOUND")

    # --- 同名分店（FR-016a）---
    print("\n[V7b] 同名連鎖分店")
    chain = [s for s in allb["stores"] if "連鎖健康餐盒" in s["name"]]
    check("兩家同名分店各自列出", len(chain) == 2, f"{len(chain)} 家")
    check("以地址區分", len({s["address"] for s in chain}) == 2)
    check("id 各自獨立", len({s["id"] for s in chain}) == 2)

    # --- V10：唯讀（FR-029）---
    print("\n[V10] 唯讀範圍")
    for method, path in [
        ("POST", "/stores"),
        ("DELETE", f"/stores/{bento['id']}"),
        ("PATCH", f"/stores/{bento['id']}"),
        ("POST", f"/stores/{bento['id']}/menu-items"),
    ]:
        r = c.request(method, f"{API}{path}", headers=auth)
        check(f"{method} {path} 不存在", r.status_code in (404, 405), f"實際 {r.status_code}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"通過 {passed}/{total}")
    if passed != total:
        print("\n失敗項目：")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name} {detail}")
    return 0 if passed == total else 1


def main() -> int:
    token, user_id = make_user()
    auth = {"Authorization": f"Bearer {token}"}
    c = httpx.Client(timeout=20.0)
    try:
        return run_checks(c, auth)
    finally:
        c.close()
        drop_user(user_id)


if __name__ == "__main__":
    sys.exit(main())
