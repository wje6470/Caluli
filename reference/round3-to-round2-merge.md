# 第三輪合併說明（回覆 round2-to-round3-sync.md）

**來源**：第三輪（`feature/round3-admin`，管理員角色與店家／餐點後台）
**回覆對象**：`reference/round2-to-round3-sync.md`（2026-08-04）
**狀態**：第三輪 implement 已完成，**尚未合併回 `main`**

---

## 一、回覆你們提出的三件事

### ✅ A. `address` nullability — 沒問題，不用改

我們寫入端是 `NOT NULL VARCHAR(500)`，你們讀取端型別維持可空。

**這個組合完全沒有問題**，也不需要對齊。寫入端保證的是「一定有值」，讀取端寬容一點只是多一條永遠走不到的分支，成本為零；而且我們日後若真的放寬約束，你們不用跟著改。

### ✅ B. `test_auth.py` 的絕對總數斷言 — 已修，謝謝提醒

**這個警告直接抓出我們自己的一個 bug。**

我們先照你們的方法重現：往測試資料庫植入**一筆**已提交的 `users` 資料，結果

```
3 failed, 4 passed   ← tests/integration/test_auth.py
```

完全如你們所述。而且我們**自己也犯了同一個錯**——`tests/integration/test_admin_role_sync.py` 照抄了那個模式，同樣掛掉。

我們採用了你們建議的第二個方案（按 `line_user_id` 過濾），而不是 autouse fixture 清表：

```python
- assert db_session.query(User).count() == 1
+ assert db_session.query(User).filter(User.line_user_id == LINE_SUB).count() == 1
```

理由是這樣**斷言其實變得更精確**——原本的寫法連「資料庫裡有沒有其他使用者」都一起斷言了，那不是這支測試要驗的事。清表方案會讓測試依賴「表是空的」這個外部狀態，過濾方案則完全自足。

改動範圍：

| 檔案 | 改動 |
|---|---|
| `tests/integration/test_auth.py` | 3 處（第一輪檔案，+5/-3，僅測試斷言，未動 API 行為） |
| `tests/integration/test_admin_role_sync.py` | 1 處（我們自己的檔案） |

驗證：**殘留資料存在時 172 passed，清空後也 172 passed**。

你們的 `seed_stores.py` 產生的 15 家店 / 47 筆餐點現在不會再讓任何測試失敗。

### ✅ C. 行為約定進契約檔 — 已經做了，你們合併後就會看到

你們看到的 `reference/shared-schema-store-menu.md` 是 **17 行**的原始版本；我們分支上是 **78 行**。

我們在 2026-08-04 已補上「欄位語意補充」五點，正好涵蓋你們列的每一條：

| 你們列的 | 契約檔的對應段落 |
|---|---|
| 座標選填且保證成對 | 第 1 點（含「讀取端務必處理 NULL」與排序行為約定） |
| `name` 不唯一 | 第 4 點（含「不同店家同名餐點各自獨立」） |
| 實刪除 + CASCADE、無軟刪除 | 第 5 點（含「讀取端不需要也不應該加排除已刪除的條件」） |
| 營養值 `0` 與 `NULL` 語意不同 | 第 2 點（含「讀取端須區分無資料與 0，NULL 不納入計算」） |
| （另補）主鍵型別 | 第 3 點 UUID |

另有「變更紀錄」段落記載每次變更的原因與對雙方的影響。合併後這份檔案就是雙方共同的權威來源，不需要再靠交接說明傳遞。

---

## 二、我們這邊的最終狀態

### 資料表（已建立，migration `0002`）

```
stores      id, name, address, latitude, longitude, created_at, updated_at
menu_items  id, store_id, name, calories, protein_g, carbs_g, fat_g, created_at, updated_at
```

**與共用契約逐字相符，零增減、零更名。** 實際 schema 已對 PostgreSQL 16 驗證：

| 約束 | 內容 |
|---|---|
| `ck_stores_coords_paired` | `(latitude IS NULL) = (longitude IS NULL)` |
| `ck_stores_latitude_range` | `latitude IS NULL OR latitude BETWEEN -90 AND 90` |
| `ck_stores_longitude_range` | `longitude IS NULL OR longitude BETWEEN -180 AND 180` |
| `ck_menu_items_*` | 四個營養欄位各一條 `>= 0`（NULL 可寫入，CHECK 對 NULL 求值為 UNKNOWN） |
| 外鍵 | `menu_items.store_id → stores.id ON DELETE CASCADE` |
| 索引 | `ix_menu_items_store (store_id)` |

`stores` 刻意**不建額外索引**——數十至數百筆，全表掃描成本可忽略，過早建索引只增加寫入成本。你們若因距離查詢需要，屆時另行評估。

### 檔案

| 類別 | 檔案 | 與你們的關係 |
|---|---|---|
| Migration | `alembic/versions/20260804_0002_stores_menu_items.py` | ✅ 保留我們的（你們的已刪除） |
| Model | `db/models/store.py`、`db/models/menu_item.py` | 🟡 同檔名，**合併取我們的**（依你們的提議） |
| 寫入服務 | `services/admin_stores.py` | ✅ 不衝突（已為你們改名） |
| 名單核對 | `services/admin_roles.py` | ✅ 不衝突 |
| 端點 | `api/v1/admin_session.py`、`admin_stores.py`、`admin_menu_items.py` | ✅ 不衝突 |
| 驗證錯誤轉換 | `api/v1/admin_route.py` | ✅ 不衝突（見下方注意事項） |
| Schema | `schemas/admin.py` | ✅ 不衝突 |
| 測試 | `tests/unit/test_admin_roles.py`、`tests/integration/test_admin_access_control.py`、`test_admin_role_sync.py`、`test_admin_stores.py` | ✅ 不衝突 |
| 前端 | `app/admin/*`、`components/admin/*` | ✅ 不衝突 |

### 同檔追加（保留雙方）

| 檔案 | 我們加的 |
|---|---|
| `db/models/__init__.py` | `Store`、`MenuItem` 匯出（與你們相同，留一份） |
| `core/config.py` | `admin_line_user_ids`（管理員名單）+ `admin_line_user_id_set` property |
| `main.py` | `v1.include_router(admin_session / admin_stores / admin_menu_items)` |
| `frontend/src/lib/api/types.ts` | `AdminSession`、`Store`、`StoreWithCount`、`StoreInput`、`MenuItem`、`MenuItemInput` |
| `frontend/src/lib/api/endpoints.ts` | `adminApi`（`me` / `stores` / `menuItems`） |
| `.env.example` | `ADMIN_LINE_USER_IDS` |

> ⚠️ **前端型別可能重複**：我們與你們都會宣告 `Store` 與 `MenuItem`。合併時留一份即可，但請注意我們的宣告把**數值欄位標為 `string`**（理由見下方注意事項 2）。若你們宣告成 `number`，兩者不能只留一份——需要先對齊。

### 我們對外的 API（你們不會用到，僅供對照）

```
GET    /api/v1/admin/me
GET    /api/v1/admin/stores
POST   /api/v1/admin/stores
GET    /api/v1/admin/stores/{id}
PATCH  /api/v1/admin/stores/{id}
DELETE /api/v1/admin/stores/{id}
GET    /api/v1/admin/stores/{id}/menu-items
POST   /api/v1/admin/stores/{id}/menu-items
PATCH  /api/v1/admin/menu-items/{id}
DELETE /api/v1/admin/menu-items/{id}
```

全部掛在 `/api/v1/admin` 前綴下，與你們的 `/api/v1/stores`（唯讀）完全分開。權限檢查掛在 router 建構參數上，有測試對全部 10 支端點逐一斷言「一般使用者一律 403 且回應內容逐字相同」。

### 驗證狀態

```
後端  pytest 172 passed（對真實 PostgreSQL 16.14，0 skipped）    ruff clean
      quickstart 六項驗證的自動化部分 31/31 passed
前端  vitest 22 passed    tsc clean    eslint clean    next build 通過
```

---

## 三、需要你們注意的三件事

### 🟡 1. 我們改了一個第一輪的檔案

`backend/tests/integration/test_auth.py`，3 處斷言（見上方 B）。**只動測試斷言，沒有動任何 API 行為或 schema。**

如果你們合併時在這個檔案遇到衝突，取我們的版本即可——過濾式斷言在你們的 seed 資料存在時也能通過。

### ✅ 2. 數值型別 — 已依你們的決定改為 JSON number（2026-08-04 更新）

**你們的四點論證我們全部接受，本輪已改完。**

原本我們選 string 的理由是「與第一輪保持一致」，但你們指出的第 3 點才是決定性的——憲章原則 III 明訂四端呼叫同一組 API 且契約一致，Dart／Swift 端逐欄 `parse` 的成本會乘以客戶端數量。我們只考慮了單一 API 內部的一致性，沒有把四端成本算進去。

第 1 點也證實了：第一輪的 `formatGrams` 是 `(Math.round(value * 10) / 10).toFixed(1)`，宣告 `value: number` 卻能吃字串，純粹是因為 `value * 10` 先隱式轉型——**能跑是運氣，不是設計**。

已改動：

| 項目 | 改法 |
|---|---|
| `schemas/admin.py` | `StoreOut` / `MenuItemOut` 的數值欄位 `Decimal` → `float`（輸入 schema 維持 `Decimal`，ge/le 驗證照舊） |
| `contracts/admin-api.yaml` | 數值欄位改回 `type: number` |
| `frontend/.../types.ts` | `Store`、`MenuItem` 及 Input 型別 `string` → `number` |
| 前端運算處 | 移除多餘的 `Number()`；表單初始化改用 `?.toString() ?? ''` |
| 測試 | 新增 3 支 JSON 原生型別斷言 |

**你們建議的 isinstance 護欄我們加了，而且它立刻證明了自己的價值。**

我們做了突變測試：把輸出 schema 改回 `Decimal`，然後分別跑新舊測試——

```
舊的 float(x) 斷言    47 passed    ← 完全沒抓到
新的 isinstance 護欄   3 failed    ← 抓到了
```

跟你們遇到的情況一模一樣：`float("620.00")` 與 `float(620.0)` 都會通過，所以那 47 支測試對這種退化完全免疫。這道護欄不是可有可無。

> ⚠️ **仍未解決：第一輪的端點還是回字串**（`/me/profile` 的 `height_cm` 回 `"175.0"`），而它自己的契約與前端型別都宣告 `number`。
>
> 我們追過第一輪每一條會用到這些值的路徑：全部恰好避開了地雷（都用 `Math.round()`、乘法這類會隱式轉型的寫法，沒有任何一處直接對 API 值呼叫 `.toFixed()`）。**現在不會壞，但那是碰巧，不是設計**——TypeScript 不會警告，下一個人寫一行 `.toFixed()` 就會複製你們遇到的整頁崩潰。
>
> FR-043 不允許本輪修改第一輪，已與需求方確認**合併完成後另行處理**。完整分析（為什麼現在沒壞、哪一行是唯一的真地雷、要改哪 24 個欄位、驗證方式）記錄於 **[known-issues.md](./known-issues.md) KI-001**，接手時不必重新調查。

### 🟡 3. 管理端有自己的驗證錯誤格式，第一輪端點不受影響

第一輪沒有註冊 `RequestValidationError` handler，驗證失敗回的是 FastAPI 預設的 `{"detail": [...]}`，而非本專案的錯誤信封。前端的 `parseError()` 解析不出來，會退回通用訊息。

我們需要管理員在表單填錯時看到具體原因（FR-047），但全域加 handler 會改變第一輪端點的行為，所以做了 `api/v1/admin_route.py`（自訂 `route_class`），**範圍精確限縮在管理端 router**。

管理端現在回：

```json
{"error":{"code":"VALIDATION_ERROR","message":"緯度與經度必須同時填寫，或同時留空。","retryable":false}}
```

**第一輪與你們的端點完全不受影響**（我們實測對照過）。你們若也想要這個行為，掛上同一個 `route_class` 即可，不需要動全域設定。

---

## 四、合併檢查清單（雙方合意版本）

1. ✅ 保留第三輪的 `20260804_0002_stores_menu_items.py`（第二輪的已刪除）
2. ✅ 保留第三輪的 `db/models/store.py` 與 `menu_item.py`，覆蓋第二輪的
3. ✅ `db/models/__init__.py`、`core/config.py`、`main.py` 保留雙方追加
4. ✅ 前端 `types.ts` / `endpoints.ts` 保留雙方追加。`Store` / `MenuItem` 型別**雙方均已統一為 `number`**，可直接留一份（原本的分歧已解決，見注意事項 2）
5. ✅ `main.py` 的 catch-all 404 路由必須維持在**所有 router 註冊之後**
6. ✅ `test_auth.py` 取第三輪版本（過濾式斷言）
7. ✅ 合併後 `reference/shared-schema-store-menu.md` 取第三輪版本（78 行，含行為約定）
8. 合併後跑一次雙方全部測試：**175（第三輪）+ 138（第二輪）**，扣除重疊
9. ✅ `api/v1/admin_route.py` 你們要沿用沒問題——它不含任何管理端專屬邏輯，就是把 `RequestValidationError` 轉成本專案的錯誤信封。掛 `route_class=AdminAPIRoute` 到你們的 router 即可。若覺得名稱綁 admin 不妥，合併後改名為 `envelope_route.py` 之類我們沒意見

### 合併後建議立刻驗證的三件事

```bash
alembic upgrade head          # 應為單一線性鏈 0001 → 0002，無雙 head
pytest                        # 兩輪測試皆通過，且 0 skipped
pytest tests/integration/test_admin_access_control.py -v    # 憲章原則 IV 必測情境
```

第三支特別重要：它會比對 ADMIN_ENDPOINTS 清單與 FastAPI 實際註冊的路由，**若合併過程中有任何管理端端點漏掉權限檢查，這支會失敗**。
