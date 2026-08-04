"""本輪只提供唯讀查詢的護欄（tasks.md T050）。

新增／修改／刪除店家與餐點屬**第三輪管理員後台**的範圍。本輪不實作也不
預留寫入端點（spec FR-029），避免與第三輪重複或衝突。

這支測試的存在理由是防止日後「順手」加上寫入端點——那在合併時會與第三輪
的實作直接衝突，且不會有任何編譯或執行期錯誤提醒。

刻意放在 unit/ 而非 integration/：只讀 OpenAPI schema，不需要資料庫，
因此在任何環境都跑得到（沒有 Docker 時整合測試會 skip）。
"""

from app.main import app

WRITE_METHODS = {"post", "put", "patch", "delete"}


def _store_paths() -> dict:
    schema = app.openapi()
    return {
        path: item
        for path, item in schema["paths"].items()
        if "/stores" in path
    }


def test_store_endpoints_exist():
    """先確認測試本身有效——若路徑消失，下面的斷言會空轉而永遠通過。"""
    paths = _store_paths()

    assert any(p.endswith("/stores") for p in paths)
    assert any(p.endswith("/menu-items") for p in paths)


def test_no_write_methods_on_store_endpoints():
    """/stores 相關路徑下只能有 GET（spec FR-029）。"""
    offenders = []
    for path, item in _store_paths().items():
        for method in item:
            if method.lower() in WRITE_METHODS:
                offenders.append(f"{method.upper()} {path}")

    assert offenders == [], (
        f"本輪不得提供店家／餐點的寫入端點（FR-029），但發現：{offenders}。"
        "資料寫入由第三輪管理員後台負責。"
    )


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
