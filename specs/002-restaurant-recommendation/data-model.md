# Data Model: 推薦餐廳（第二輪）

**Date**: 2026-08-04 | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

資料庫：PostgreSQL（Supabase）。沿用第一輪慣例：UUID 主鍵（`gen_random_uuid()`）、時間欄位 `TIMESTAMPTZ` 存 UTC。

> ## ⚠️ 本文件的欄位集合受共用契約約束
>
> `stores` 與 `menu_items` 的**欄位名稱與數量**完全依照
> [reference/shared-schema-store-menu.md](../../reference/shared-schema-store-menu.md)，
> 由本輪（讀）與第三輪管理員後台（寫）共用。本輪**不得**增減欄位或改名。
>
> **2026-08-04 第三輪交接更新已併入本文件**：`menu_items` 補上 `created_at`／`updated_at`
> （OQ-4 結案）、座標確認為選填（OQ-2 部分結案）、`ON DELETE CASCADE` 確認（OQ-5 結案）、
> 確認無軟刪除欄位、確認名稱不具唯一性、確認營養值 0 為有效數值。
>
> **2026-08-04 第三輪執行清單已給出最終定義，全部 Open Question 結案**：
> 主鍵 UUID、營養欄位 nullable、`address` 為 **NOT NULL VARCHAR(500)**、
> `name` 為 VARCHAR(255) 且不唯一、經緯度 nullable 且以 CHECK 保證成對、
> `ON DELETE CASCADE`。下表已依此更新，**不再有待對齊項目**。
>
> **⚠️ 建表歸屬已定：由第三輪建立**。`stores` / `menu_items` 的 migration 與
> model 由 `feature/round3-admin` 提供（他們負責寫入）。本輪已**刪除**自己的
> migration，model 保留為合併前的可執行鏡像，合併時直接採用對方版本
> ——詳見本文件末的「Migration 與 model 歸屬」。
>
> 本輪依賴的是 `from app.db.models import Store, MenuItem` 這個匯入介面，
> 第三輪已保證其穩定，與檔案怎麼切無關。

## 資料表總覽

```text
stores ──1:N── menu_items

   ╳ 與第一輪的任何資料表【無外鍵、無關聯、無共用】
   ╳ 特別是與 food_nutrition_references 之間，禁止任何方向的參照
```

> **憲章原則 V 落實點**：`menu_items` 是「特定店家／餐點之營養值」，
> `food_nutrition_references` 是「拍照辨識用之通用食物營養對照表」。兩者為
> 兩套獨立資料，即使餐點名稱與食物名稱相同也**不查詢、不連動、不建立外鍵**
> （FR-030、FR-031）。本輪 migration 不得觸碰第一輪的任何資料表。

---

## stores

收錄的餐飲店家。本輪**唯讀**；寫入由第三輪管理員後台負責。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | 與第一輪全專案的主鍵慣例一致 |
| `name` | VARCHAR(255) | NOT NULL | 店家名稱。**不具唯一性**——連鎖分店同名為正常資料，以 `address` 區分。測試資料以 `[測試]` 前綴標示（[research.md](./research.md) R-09） |
| `address` | VARCHAR(500) | **NOT NULL** | 地址。**是分辨同名分店的唯一依據**，故清單必須顯示（FR-016）。僅供顯示，不參與距離計算，且系統不驗證其與座標是否一致 |
| `latitude` | NUMERIC(9,6) | **NULL** | 緯度。**選填**——後台允許只建「名稱＋地址」、暫不填座標的店家，故 NULL 是常態而非異常 |
| `longitude` | NUMERIC(9,6) | **NULL** | 經度。以 CHECK `(latitude IS NULL) = (longitude IS NULL)` 於 DB 層保證與 `latitude` 成對 |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |

**索引**：`id` 的 PK 索引即足夠。本輪不建立經緯度索引——距離計算在應用層進行（R-01），資料庫端沒有可利用索引的述詞；建了也不會被用到。

**型別選擇說明**：經緯度採 `NUMERIC(9,6)` 而非 `DOUBLE PRECISION`。六位小數約 0.11 公尺精度，遠超本用途所需，且 `NUMERIC` 與第一輪所有數值欄位的慣例一致（避免同一資料庫內兩套浮點語意）。Python 端取出為 `Decimal`，計算 Haversine 前轉 `float`。

**驗證規則**

- 緯度與經度**同時有值或同時為 NULL**，由 DB 層 CHECK 約束 `(latitude IS NULL) = (longitude IS NULL)` 保證，寫入端另行擋下。本輪讀取端仍保留防禦性檢查（`lat is None or lng is None` 即視為無座標），成本為零且不需為此設計使用者可見的錯誤情境。
- 無座標的店家：**排除**於距離排序結果之外（沒有距離可算，補在末端會讓使用者要求「附近」時混入與距離無關的店家），但在不排序的全部店家清單中**正常出現**（FR-018）。此為雙方明確議定的行為。
- **不得以 `name` 作為識別或查詢鍵**（FR-016a）。店名不唯一，清單的 React key、路由參數與所有查詢一律使用 `id`。
- 本輪**不提供**任何建立、修改、刪除 `stores` 的 API（FR-029）。

**對應需求**：FR-013、FR-014、FR-016、FR-017、FR-018、FR-028

---

## menu_items

店家登錄的餐點及其營養數值。本輪**唯讀**。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | |
| `store_id` | UUID | NOT NULL, FK → `stores.id` **ON DELETE CASCADE** | 刪除店家連帶刪除其全部餐點，不留孤兒資料 |
| `name` | VARCHAR(255) | NOT NULL | 餐點名稱。**不具唯一性**——同店家內允許同名餐點，各自獨立 |
| `calories` | NUMERIC(7,2) | **NULL**, CHECK `>= 0` | 熱量（大卡），**每份餐點**的數值 |
| `protein_g` | NUMERIC(6,2) | **NULL**, CHECK `>= 0` | 蛋白質（公克） |
| `carbs_g` | NUMERIC(6,2) | **NULL**, CHECK `>= 0` | 碳水化合物（公克） |
| `fat_g` | NUMERIC(6,2) | **NULL**, CHECK `>= 0` | 脂肪（公克） |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | 2026-08-04 交接新增，與 `stores` 一致。由寫入端自動填入 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` | 同上。本輪不讀取、不對外呈現 |

**索引**：`ix_menu_items_store (store_id)` — 唯一的查詢路徑是「取某店家的全部餐點」。

**驗證規則**

- 四個營養欄位**必須允許 NULL**，且 `0` 與 `NULL` 是**兩種不同的有效狀態**：
  - `0` → 店家登錄該營養素為零 → 畫面顯示 **`0`**
  - `NULL` → 店家未提供 → 畫面顯示 **「無資料」**

  這是 FR-025 的前提。若以 NOT NULL + 預設 0 建表，「未填寫」與「確實為 0」的區別在寫入當下即永久喪失（[research.md](./research.md) R-08）。**已於 2026-08-04 第三輪執行清單確認為 nullable，且對方有測試專門斷言「NULL 營養值不會被寫成 0」**。
- 營養值不接受負數（CHECK `>= 0`）。
- **不得以 `name` 識別餐點**，同店家內可能有同名餐點；不同店家的同名餐點數值互不連動（FR-031）。
- 本輪**不提供**任何建立、修改、刪除 `menu_items` 的 API（FR-029）。

**對應需求**：FR-021〜FR-025、FR-028、FR-030、FR-031

---

## 衍生值：距離（不入庫）

`StoreDistance` 是查詢時計算的衍生值，**不儲存於任何資料表**，也不快取。

- 計算方式：Haversine 大圓距離，地球半徑取 6371.0088 km（IUGG 平均半徑）。
- 計算位置：`app/services/geo.py` 的純函式（[research.md](./research.md) R-01）。
- 輸入：使用者當次座標（`UserLocation`，暫時性查詢輸入，**不入庫、不記錄**，FR-012）與店家座標。
- 輸出：API 以 `distance_m`（公尺，整數）回傳；全部模式下為 `null`。

---

## 查詢管線（順序不可調換）

`GET /stores?lat=&lng=` 的處理順序固定如下（[research.md](./research.md) R-04）：

```text
1. 取出全部 stores
2. 排除 latitude 或 longitude 為 NULL 者          ← FR-018
3. 對其餘每筆計算 haversine 距離
4. 過濾 distance > 5.0 km 者                      ← FR-020
5. 依距離升冪排序                                  ← FR-014
6. 取前 10 筆                                      ← FR-014
7. 附上 total_store_count（步驟 1 的總筆數，未經任何過濾）← R-05
```

步驟 4 必須早於 6：先取 10 筆再過濾半徑會得到錯誤的少於 10 筆結果；步驟 2 必須早於 3，否則 NULL 座標會使計算失敗或被當作 (0,0) 排到最前。

`GET /stores`（無座標）僅執行步驟 1 與 7，依 `name` 升冪排序（穩定且可預期，spec Assumptions）。

---

## 資料隔離與憲章合規

| 檢查項 | 落實方式 |
|---|---|
| 與通用食物營養對照表無外鍵 | 本輪 migration 僅建立 `stores`、`menu_items` 兩張表，其外鍵只有 `menu_items.store_id → stores.id` |
| 不合併、不以型別欄位混存 | 兩張新表與 `food_nutrition_references` 無任何欄位交集或參照 |
| 查詢路徑獨立 | `app/services/stores.py` 不 import 任何第一輪的營養相關模組（可由測試斷言） |
| 不修改第一輪資料表 | migration `0002` 的 `upgrade()` 只有 `create_table`，無任何 `alter_table`（FR-032） |
| 使用者資料隔離 | 店家與餐點對所有登入使用者相同，**不含** `user_id`，也不需要按使用者過濾 |
| 無軟刪除過濾 | 資料表無 `deleted_at`／`is_active` 欄位，刪除為實刪除。查詢**不得**加任何「排除已刪除」條件（FR-018a）——那會成為未來每支查詢都可能漏加的過濾條件 |

---

## Migration 與 model 歸屬

**兩張表的 DDL 由第三輪（`feature/round3-admin`）提供**——他們負責寫入，本輪只讀，
由寫入方持有 schema 定義是正確的歸屬。依 2026-08-04 第三輪執行清單：

| 項目 | 歸屬 | 本輪的處置 |
|---|---|---|
| `alembic/versions/20260804_0002_stores_menu_items.py`（revision `0002`） | 第三輪 | 本輪原有的 `20260804_0002_store_menu.py` **已刪除**——兩支同為 `0002` 且同以 `0001` 為 parent，合併後必然雙 head 且重複建表 |
| `app/db/models/store.py`（`Store`） | 第三輪 | 本輪保留同名同結構的鏡像，**合併時採用對方版本** |
| `app/db/models/menu_item.py`（`MenuItem`） | 第三輪 | 同上 |

**本輪為何仍保留 model 檔案**：若直接刪除，第二輪分支在合併前將無法執行任何測試、
seed 或本機驗證（136 支後端測試全數失敗）。故保留為**可執行的鏡像**，欄位逐項比照
第三輪的最終定義，合併時直接覆蓋即可，本輪的查詢程式碼一行都不用改。

**本輪依賴的介面**：`from app.db.models import Store, MenuItem`。第三輪已保證此匯入
路徑穩定，與檔案怎麼切無關——因此 `services/stores.py`、`api/v1/stores.py`、
`scripts/seed_stores.py` 與全部測試都不受對方的檔案組織方式影響。

**合併前建表（本機開發）**：本輪已無 migration，測試由 `conftest.py` 的
`Base.metadata.create_all()` 建表，不受影響；若要跑 `seed_stores.py`，需先以
`create_all()` 或第三輪的 migration 建表。
