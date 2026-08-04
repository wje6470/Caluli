# 給第三輪的回覆與同步事項

**來源**：第二輪（`feature/round2-restaurant`，推薦餐廳／唯讀查詢）
**回覆對象**：第三輪執行清單（2026-08-04）
**狀態**：第二輪 implement 已完成，**尚未合併回 `main`**

---

## 一、你們的四個確認項

### ✅ 1. migration 已刪除

`backend/alembic/versions/20260804_0002_store_menu.py` 已從本分支移除。
`alembic heads` 目前是 **`0001` 單一 head**，你們的 `0002` 可以直接接上。

同意你們的判斷——我們只讀不寫，本來就不該持有這張表的 DDL。

### ⚠️ 2. model 沒有直接刪除，改成與你們相同的拆檔方式

**這一項請確認你們接受。**

直接刪除會讓本分支在合併前完全跑不動：136 支後端測試全部失敗、seed 不能執行、無法做任何本機驗證。所以改成：

```
backend/app/db/models/store.py       → Store（僅此一個）
backend/app/db/models/menu_item.py   → MenuItem（僅此一個）
```

與你們的組織方式一致，欄位**逐項比照你們的最終定義**（含 `CHECK ((latitude IS NULL) = (longitude IS NULL))`、`address VARCHAR(500) NOT NULL`、索引名 `ix_menu_items_store`）。兩個檔案的檔頭都寫明「合併時以第三輪版本為準，本檔可直接覆蓋」。

**合併時直接 take yours 即可**，我們的查詢程式碼一行都不用改——依賴的就是你們保證的 `from app.db.models import Store, MenuItem`。

### ✅ 3. `VARCHAR(255)` 沒問題

我們原本寫的就是 `String(255)`（規格文件裡寫 TEXT 是筆誤，已更正）。不需要改。

### 🔴 4. 我們**尚未**合併回 `main`

`feature/round2-restaurant` 仍是獨立分支，`main` 上沒有 `stores` / `menu_items`。

**請照你們的階段 2 正常建表**，不需要改成核對既有結構。

---

## 二、需要你們注意的三件事

### 🟡 A. `address` 的 nullability 變更（我們已配合，但你們要知道）

先前的交接說明沒提到這一欄，我們原本假設可空；現在依你們的定義改為 `NOT NULL VARCHAR(500)`。

不過**我們的讀取端型別刻意維持可空**（`StoreOut.address: str | None`、前端 `string | null`）：

- 行為完全不變（前端本來就有 `?? '地址未提供'` 的退路）
- 我們不再擁有這張表，寬容的讀取型別成本為零
- 你們日後若放寬約束，我們不用跟著改

FR-016「地址必須顯示」因為 NOT NULL 反而更有保障——地址是分辨同名分店的唯一依據。

### 🔴 B. 第一輪的 `test_auth.py` 會被你們的 admin 使用者弄壞

**這是我們踩到的坑，你們幾乎一定會踩到同一個。**

`backend/tests/integration/test_auth.py` 有三支測試以**絕對總數**斷言：

```python
assert db_session.query(User).count() == 1   # line 93, 111
```

任何**已提交**到測試資料庫的 `users` 資料都會讓這三支失敗。我們的冒煙測試建立了 2 個使用者，結果就是 `3 failed, 133 passed`。

你們的階段 1（權限層 + 管理員指派）會建立 admin 使用者，如果有任何一支測試或腳本 commit 了使用者，就會撞到。

**我們的處理方式**（可參考）：

- `tests/smoke_stores.py` 在 `finally` 區塊刪除自己建立的使用者
- 自己的整合測試加 autouse fixture，在**測試交易內**清空相關資料表，靠 rollback 還原：

```python
@pytest.fixture(autouse=True)
def _isolate_store_tables(db_session):
    db_session.query(MenuItem).delete()
    db_session.query(Store).delete()
    db_session.flush()
```

這樣可以直接在已 seed 的本機資料庫上跑測試，不必另外準備乾淨的庫。

**建議**：如果你們也覺得那三支測試的絕對總數斷言太脆，或許值得一起改成「按 `line_user_id` 過濾」而不是全表計數。這是第一輪的檔案，我們沒有動它。

### 🟡 C. 行為約定還沒進到共用契約檔案

`reference/shared-schema-store-menu.md` 目前只有欄位清單。但真正約束實作的是這些**行為約定**，它們只存在於兩份交接說明裡：

- 座標選填、且保證成對（現在有 DB CHECK 了，很好）
- `name` 不唯一（連鎖分店同名 → 讀取端不得以 name 識別或去重）
- 實刪除 + CASCADE、無軟刪除欄位（→ 查詢不得加「排除已刪除」條件）
- 營養值 `0` 是有效數值，與 `NULL` 語意不同

日後只讀契約檔案的人看不到這些，而**每一條都會改變讀取端的寫法**。

我們已完整記錄在 `specs/002-restaurant-recommendation/data-model.md`，你們建表時可以直接取用補進契約檔案。這是共用檔案，我們沒有擅自修改。

---

## 三、我們這邊的最終狀態（供你們對照）

### 檔案

| 類別 | 檔案 | 與你們的關係 |
|---|---|---|
| Model | `db/models/store.py`、`db/models/menu_item.py` | 🟡 同檔名，合併取你們的 |
| Migration | 無 | ✅ 已刪除 |
| 查詢服務 | `services/stores.py` | ✅ 不衝突（你們已改名 `admin_stores.py`，謝謝） |
| 距離計算 | `services/geo.py` | ✅ 不衝突 |
| 端點 | `api/v1/stores.py`（僅 GET） | ✅ 不衝突 |
| Schema | `schemas/store.py` | ✅ 不衝突 |
| 測試資料 | `scripts/seed_stores.py`（含 `--purge`） | ✅ 不衝突 |
| 測試 | `tests/unit/test_geo.py`、`test_stores_query.py`、`test_stores_readonly.py`、`test_nutrition_isolation.py`、`test_seed_stores_composition.py`、`tests/integration/test_stores_api.py`、`tests/smoke_stores.py` | ✅ 不衝突 |
| 前端 | `app/(app)/restaurants/*`、`components/restaurants/*`、`components/ui/PermissionNotice.tsx`、`lib/geo/`、`lib/format/`、`hooks/useCurrentLocation.ts` | ✅ 不衝突 |

### 同檔追加（保留雙方即可）

| 檔案 | 我們加的 |
|---|---|
| `db/models/__init__.py` | `Store`、`MenuItem` 匯出（內容應與你們相同，留一份） |
| `core/config.py` | `nearby_radius_km = 5.0`、`nearby_limit = 10` |
| `main.py` | `v1.include_router(stores.router)`，位置在 `foods.router` 之後、catch-all 404 之前 |
| `frontend/src/lib/api/types.ts` | `Store`、`MenuItem`、`StoreListResponse`、`MenuItemListResponse` |
| `frontend/src/lib/api/endpoints.ts` | `storeApi`（`list` / `get` / `menuItems`） |

### 我們對外的 API（你們的後台不需要用，僅供對照）

```
GET /api/v1/stores                      # 附近模式（帶 lat/lng）或全部模式
GET /api/v1/stores/{id}
GET /api/v1/stores/{id}/menu-items
```

**只有 GET**，有測試（`test_stores_readonly.py`）以 OpenAPI schema 斷言不存在任何寫入方法，防止日後有人順手加上而與你們衝突。

### 驗證狀態

```
後端  pytest 136 passed（對真實 PostgreSQL 16.4）    ruff clean
      真實 HTTP 冒煙測試 39/39
前端  vitest 68 passed    tsc clean    eslint clean    next build 12 routes
```

`seed_stores.py` 產生 15 家測試店家 / 47 筆餐點，全部以 `[測試]` 前綴標示，`--purge` 可精準清除（餐點靠你們的 CASCADE 連帶刪除，已實測）。

你們的後台上線後，這支腳本就降為「快速鋪測試資料」的工具，不再是唯一資料來源。

---

## 四、合併時的檢查清單

1. 保留你們的 `20260804_0002_stores_menu_items.py`（我們的已刪除）
2. 保留你們的 `db/models/store.py` 與 `menu_item.py`，覆蓋我們的
3. `db/models/__init__.py`、`core/config.py`、`main.py`、前端 `types.ts` / `endpoints.ts` 保留雙方追加
4. `main.py` 的 catch-all 404 路由必須維持在**所有 router 註冊之後**
5. 合併後跑一次雙方的測試；若 `test_auth.py` 那三支失敗，多半是資料庫裡有殘留的 `users`（見上方 B）
6. 建議把行為約定補進 `shared-schema-store-menu.md`（見上方 C）
