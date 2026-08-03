"""真實 HTTP 冒煙測試（T122／T123 的自動化部分）。

對**實際運行中**的服務執行，涵蓋 quickstart.md 的 V3〜V8 後端路徑：
辨識 → 份量換算 → 儲存 → 儀表板 → 趨勢 → 編輯 → 刪除，並量測回應時間。

與 pytest 整合測試的差別：那些走 ASGITransport 且在交易中 rollback；
這裡是真的 HTTP、真的資料庫寫入、真的辨識服務呼叫。

用法：
    uv run python tests/smoke_e2e.py
需先啟動 API（:8000）、辨識 stub（:8900）與 PostgreSQL。
"""

import sys
import time
import uuid
from datetime import UTC, datetime

import httpx

from app.core.security import create_access_token
from app.db.models import User
from app.db.session import SessionLocal

API = "http://127.0.0.1:8000/api/v1"
PHOTO = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{f' — {detail}' if detail else ''}")


def make_user() -> tuple[str, uuid.UUID]:
    """直接建使用者並簽 token——LINE 登入需真實 channel，不在冒煙範圍。"""
    with SessionLocal() as db:
        user = User(line_user_id=f"Usmoke{uuid.uuid4().hex}", display_name="冒煙測試")
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _ = create_access_token(user.id)
        return token, user.id


def main() -> int:
    token, _ = make_user()
    client = httpx.Client(base_url=API, headers={"Authorization": f"Bearer {token}"}, timeout=60)

    print("\n[1] 個人資訊建檔與 TDEE 計算")
    profile = client.put(
        "/me/profile",
        json={
            "gender": "male",
            "age_years": 28,
            "height_cm": "175",
            "weight_kg": "68.5",
            "activity_level": "moderate",
        },
    )
    check("PUT /me/profile → 200", profile.status_code == 200, str(profile.status_code))
    body = profile.json()
    # 手算：BMR 1643.75 × 1.45 = 2383.44
    check("TDEE 計算正確", body["tdee_kcal"] == "2383.44", body.get("tdee_kcal", "?"))

    me = client.get("/me").json()
    check("GET /me profile_completed=true", me["profile_completed"] is True)

    print("\n[2] 辨識（normal 模式，真實呼叫辨識服務）")
    started = time.perf_counter()
    rec = client.post(
        "/recognitions",
        files={"photo": ("meal.jpg", PHOTO, "image/jpeg")},
        params={"mode": "normal"},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    check("POST /recognitions → 200", rec.status_code == 200, str(rec.status_code))
    data = rec.json()
    check("status=completed", data["status"] == "completed", data["status"])
    check("回傳品項", len(data["items"]) > 0, f"{len(data['items'])} 項")

    first = data["items"][0]
    check("★ per_100g 存在（前端即時換算的必要條件）", first.get("per_100g") is not None)
    check("★ default_portion_grams 存在", first.get("default_portion_grams") is not None)
    check("Top-K 候選存在", len(first.get("candidates", [])) > 0)
    check("辨識耗時 < 5s", elapsed_ms < 5000, f"{elapsed_ms:.0f} ms")
    recognition_id = data["id"]

    print("\n[3] ★ 未偵測到食物走成功路徑（FR-027）")
    empty = client.post(
        "/recognitions", files={"photo": ("m.jpg", PHOTO, "image/jpeg")}, params={"mode": "empty"}
    )
    check("HTTP 200（不是錯誤碼）", empty.status_code == 200, str(empty.status_code))
    eb = empty.json()
    check("status=completed", eb["status"] == "completed", eb["status"])
    check("items 為空陣列", eb["items"] == [])
    check("保留服務訊息", eb["message"] == "沒有偵測到食物，請換一張再試試", str(eb["message"]))

    print("\n[4] 錯誤分支")
    for mode, expected, code in [
        ("error", 503, "RECOGNITION_UNAVAILABLE"),
        ("garbage", 502, "RECOGNITION_BAD_RESPONSE"),
    ]:
        resp = client.post(
            "/recognitions", files={"photo": ("m.jpg", PHOTO, "image/jpeg")}, params={"mode": mode}
        )
        ok = resp.status_code == expected and resp.json()["error"]["code"] == code
        check(f"{mode} → {expected} {code}", ok, str(resp.status_code))
        if ok:
            check(f"{mode} retryable=true", resp.json()["error"]["retryable"] is True)

    print("\n[5] 上傳驗證")
    bad_type = client.post("/recognitions", files={"photo": ("x.pdf", b"%PDF", "application/pdf")})
    check("非圖片 → 415", bad_type.status_code == 415, str(bad_type.status_code))

    print("\n[6] 儲存紀錄（後端重新驗算）")
    per_100g = first["per_100g"]
    save = client.post(
        "/meal-records",
        json={
            "recognition_id": recognition_id,
            "meal_type": "lunch",
            "items": [
                {
                    "food_reference_id": first["food_reference_id"],
                    "food_name": first["name"],
                    "portion_grams": "375",
                    "default_portion_grams": first["default_portion_grams"],
                    "per_100g": per_100g,
                    "is_user_modified": True,
                }
            ],
        },
    )
    check("POST /meal-records → 201", save.status_code == 201, str(save.status_code))
    saved = save.json()
    expected_kcal = round(float(per_100g["calories_kcal"]) * 3.75, 2)
    actual_kcal = float(saved["items"][0]["nutrients"]["calories_kcal"])
    check(
        "後端換算 = per_100g × 375/100",
        abs(actual_kcal - expected_kcal) < 0.01,
        f"{actual_kcal} vs {expected_kcal}",
    )
    record_id = saved["id"]

    print("\n[7] 儀表板（含回應時間，SC）")
    started = time.perf_counter()
    dash = client.get("/dashboard")
    dash_ms = (time.perf_counter() - started) * 1000
    check("GET /dashboard → 200", dash.status_code == 200)
    db_body = dash.json()
    check("已攝取反映該筆紀錄", float(db_body["consumed"]["calories_kcal"]) == actual_kcal)
    check(
        "剩餘 = 目標 − 已攝取",
        abs(
            float(db_body["remaining"]["calories_kcal"])
            - (float(db_body["targets"]["calories_kcal"]) - actual_kcal)
        )
        < 0.01,
    )
    check("儀表板 < 500ms", dash_ms < 500, f"{dash_ms:.0f} ms")

    print("\n[8] 趨勢（30 天，含回應時間）")
    started = time.perf_counter()
    trends = client.get("/trends", params={"range_days": 30, "metric": "calories"})
    trend_ms = (time.perf_counter() - started) * 1000
    check("GET /trends → 200", trends.status_code == 200)
    tb = trends.json()
    check("回傳完整 30 天序列", len(tb["points"]) == 30, str(len(tb["points"])))
    check("今日有值", float(tb["points"][-1]["value"]) == actual_kcal)
    check("空白日為 0", all(float(p["value"]) == 0 for p in tb["points"][:-1]))
    check("30 天趨勢 < 500ms", trend_ms < 500, f"{trend_ms:.0f} ms")

    print("\n[9] 食物搜尋（T082）")
    search = client.get("/foods/search", params={"q": "飯"})
    check("GET /foods/search → 200", search.status_code == 200)
    check("有搜尋結果", len(search.json()["foods"]) > 0, f"{len(search.json()['foods'])} 筆")

    print("\n[10] 編輯與刪除，目標重算不影響歷史")
    edit = client.patch(
        f"/meal-records/{record_id}",
        json={
            "meal_type": "dinner",
            "items": [
                {
                    "food_name": first["name"],
                    "portion_grams": "100",
                    "per_100g": per_100g,
                    "is_user_modified": True,
                }
            ],
        },
    )
    check("PATCH → 200", edit.status_code == 200, str(edit.status_code))
    edited_kcal = float(edit.json()["items"][0]["nutrients"]["calories_kcal"])
    check("編輯後重算", abs(edited_kcal - float(per_100g["calories_kcal"])) < 0.01)

    client.put(
        "/me/profile",
        json={
            "gender": "male",
            "age_years": 28,
            "height_cm": "175",
            "weight_kg": "95",
            "activity_level": "high",
        },
    )
    after = client.get("/meal-records").json()["records"][0]
    check(
        "★ 目標重算不改變歷史紀錄（FR-016）",
        float(after["items"][0]["nutrients"]["calories_kcal"]) == edited_kcal,
    )

    check("DELETE → 204", client.delete(f"/meal-records/{record_id}").status_code == 204)
    check(
        "刪除後合計歸零", float(client.get("/dashboard").json()["consumed"]["calories_kcal"]) == 0
    )

    print("\n[11] 資料隔離（FR-044）")
    other_token, _ = make_user()
    other = httpx.Client(base_url=API, headers={"Authorization": f"Bearer {other_token}"})
    check("他人辨識資源 → 404", other.get(f"/recognitions/{recognition_id}").status_code == 404)
    check("未帶 token → 401", httpx.get(f"{API}/me").status_code == 401)

    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{'=' * 60}")
    print(f"通過 {len(results) - len(failed)} / {len(results)}")
    if failed:
        print("失敗項目：")
        for name in failed:
            print(f"  - {name}")
    print(f"[時間] 辨識 {elapsed_ms:.0f}ms ・ 儀表板 {dash_ms:.0f}ms ・ 趨勢 {trend_ms:.0f}ms")
    print(f"執行於 {datetime.now(UTC).isoformat()}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
