"""本輪只提供唯讀查詢的護欄（tasks.md T050）。

新增／修改／刪除店家與餐點屬**第三輪管理員後台**的範圍。本輪不實作也不
預留寫入端點（spec FR-029），避免與第三輪重複或衝突。

這支測試的存在理由是防止日後「順手」加上寫入端點——那在合併時會與第三輪
的實作直接衝突，且不會有任何編譯或執行期錯誤提醒。

刻意放在 unit/ 而非 integration/：只讀 OpenAPI schema，不需要資料庫，
因此在任何環境都跑得到（沒有 Docker 時整合測試會 skip）。

⚠️ 篩選範圍必須排除 `/admin/`（2026-08-04 與第三輪合併時修正）
==============================================================
第三輪的管理端在 `/api/v1/admin/stores` 提供 POST／PATCH／DELETE，那是
**預期且正確**的——寫入本來就歸它負責。本測試要守的是第二輪自己的
`/api/v1/stores`（使用者端唯讀），不是全專案任何含 "stores" 的路徑。

合併前原本的篩選條件是 `"/stores" in path`，合併後會把管理端的寫入端點
一併框進來而誤報。這裡改為明確鎖定使用者端前綴。
"""

from app.main import app

WRITE_METHODS = {"post", "put", "patch", "delete"}

#: 第二輪使用者端的唯讀前綴。管理端的 /api/v1/admin/stores 不在此範圍。
PUBLIC_STORE_PREFIX = "/api/v1/stores"


def _store_paths() -> dict:
    """僅取第二輪使用者端的店家路徑，排除第三輪管理端。"""
    schema = app.openapi()
    return {
        path: item
        for path, item in schema["paths"].items()
        if path.startswith(PUBLIC_STORE_PREFIX)
    }


def test_store_endpoints_exist():
    """先確認測試本身有效——若路徑消失，下面的斷言會空轉而永遠通過。"""
    paths = _store_paths()

    assert any(p.endswith("/stores") for p in paths)
    assert any(p.endswith("/menu-items") for p in paths)


def test_no_write_methods_on_store_endpoints():
    """使用者端 /api/v1/stores 下只能有 GET（spec FR-029）。"""
    offenders = []
    for path, item in _store_paths().items():
        for method in item:
            if method.lower() in WRITE_METHODS:
                offenders.append(f"{method.upper()} {path}")

    assert offenders == [], (
        f"第二輪的使用者端不得提供店家／餐點的寫入端點（FR-029），但發現："
        f"{offenders}。資料寫入由第三輪的 /api/v1/admin/stores 負責。"
    )


def test_writes_live_on_the_admin_side():
    """對照組：寫入端點確實存在，只是在管理端（第三輪）。

    這支測試守的是**責任分工**而非單純的「沒有寫入端點」。若哪天有人把
    篩選前綴寫錯導致 _store_paths() 回空集合，上面那支會空轉而永遠通過，
    這支則會失敗——兩者互為對照。
    """
    schema = app.openapi()
    admin_writes = {
        f"{method.upper()} {path}"
        for path, item in schema["paths"].items()
        if path.startswith("/api/v1/admin/stores")
        for method in item
        if method.lower() in WRITE_METHODS
    }

    assert admin_writes, "管理端應提供店家寫入端點（第三輪 FR-034〜FR-040）"


def test_store_endpoints_require_authentication():
    """所有店家端點都要求登入（FR-004），且沿用同一套驗證，不分岔。"""
    for path, item in _store_paths().items():
        for method, operation in item.items():
            if method.lower() != "get":
                continue
            # security 未覆寫代表沿用全域的 bearerAuth。
            assert operation.get("security", None) != [], (
                f"{method.upper()} {path} 不應停用驗證"
            )
