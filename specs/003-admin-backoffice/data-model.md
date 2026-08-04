# Phase 1 Data Model: 管理員角色與店家／餐點後台（第三輪）

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-04

**權威來源**: 店家／餐點的欄位結構完全依 [reference/shared-schema-store-menu.md](../../reference/shared-schema-store-menu.md)。本文件**不新增、不更名、不移除**該契約定義的任何欄位；下方每張表都附「契約對應」欄位供逐一核對。

---

## 既有資料表的變更

### `users` — 無結構變更

第一輪已建立 `role` 欄位，含 `CHECK role IN ('user','admin')` 與 `server_default='user'`（[user.py:34](../../backend/app/db/models/user.py#L34)）。

**本輪不做任何 migration 變更**，僅啟用其語意：登入時由 [admin_roles.py](./research.md#r-03管理員指派的實作方式) 依名單寫入 `'user'` 或 `'admin'`。

| 欄位 | 本輪的使用方式 |
|------|--------------|
| `role` | 由登入流程雙向同步；無任何 API 可寫入；`require_admin()` 依此判斷 |
| 其餘欄位 | 完全不動（FR-043） |

---

## 新增資料表 1：`stores`

**用途**：可供推薦的合作餐廳。本輪負責寫入，第二輪負責讀取。

| 欄位 | 型別 | 約束 | 契約對應 | 說明 |
|------|------|------|---------|------|
| `id` | `UUID` | PK, `server_default gen_random_uuid()` | ✅ `id` | 沿用 `uuid_pk()` 慣例 |
| `name` | `VARCHAR(255)` | `NOT NULL` | ✅ `name（店家名稱）` | **不設 UNIQUE**——連鎖分店允許同名（FR-027） |
| `address` | `VARCHAR(500)` | `NOT NULL` | ✅ `address（地址）` | FR-021 定為必填 |
| `latitude` | `NUMERIC(9,6)` | `NULL` 允許 | ✅ `latitude` | 選填，須與 `longitude` 成對（FR-021、FR-022） |
| `longitude` | `NUMERIC(9,6)` | `NULL` 允許 | ✅ `longitude` | 同上 |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `server_default now()` | ✅ `created_at` | 由 `TimestampMixin` 提供 |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, `server_default now()`, `onupdate` | ✅ `updated_at` | 同上 |

**欄位數 7，與契約完全一致，無增減。**

### 約束

```sql
CONSTRAINT ck_stores_coords_paired
  CHECK ((latitude IS NULL) = (longitude IS NULL))
CONSTRAINT ck_stores_latitude_range
  CHECK (latitude IS NULL OR (latitude BETWEEN -90 AND 90))
CONSTRAINT ck_stores_longitude_range
  CHECK (longitude IS NULL OR (longitude BETWEEN -180 AND 180))
```

命名沿用第一輪的 `ck_<table>_<意義>` 慣例。理由與型別選擇見 [R-06](./research.md#r-06座標欄位的資料庫層設計)。

### 索引

**不建立額外索引。** 店家數量為數十至數百筆，全表掃描成本可忽略；過早建索引只會增加寫入成本與 migration 複雜度。第二輪若因距離查詢需要索引，屆時另行評估（距離排序是計算後排序，一般索引也幫不上忙）。

### 驗證規則（應用層，對應 spec）

| 規則 | 來源 | 錯誤碼 |
|------|------|--------|
| `name` 非空白字串 | FR-021 | `VALIDATION_ERROR` |
| `address` 非空白字串 | FR-021 | `VALIDATION_ERROR` |
| 座標成對（同時有值或同時為 null） | FR-022 | `VALIDATION_ERROR` |
| 緯度 -90～90、經度 -180～180 | FR-023 | `VALIDATION_ERROR` |
| 目標店家不存在 | FR-028 | `NOT_FOUND` |

雙層驗證沿用第一輪慣例：pydantic 層產生可讀的中文訊息，DB CHECK 兜底。

---

## 新增資料表 2：`menu_items`

**用途**：特定店家自行登錄的餐點及其營養數值。

> ⚠️ **命名區辨**：本表的 ORM class 為 `MenuItem`，與第一輪既有的 `MealItem`（`meal_items`，飲食紀錄中的品項）**只差兩個字母但語意完全不同**。
>
> - `MealItem` = 使用者拍照記錄下來的一項食物，數值為寫入當下的快照
> - `MenuItem` = 店家菜單上的一道菜，數值為店家登錄的既定值
>
> 兩者**無任何關聯、無外鍵、不得互相參照**。撰寫 import 時務必確認取用的是哪一個。

| 欄位 | 型別 | 約束 | 契約對應 | 說明 |
|------|------|------|---------|------|
| `id` | `UUID` | PK, `server_default gen_random_uuid()` | ✅ `id` | |
| `store_id` | `UUID` | `NOT NULL`, FK → `stores.id` **ON DELETE CASCADE** | ✅ `store_id（外鍵，關聯 stores）` | 強歸屬，見 [R-07](./research.md#r-07menu_itemsstore_id-的-on-delete-規則) |
| `name` | `VARCHAR(255)` | `NOT NULL` | ✅ `name（餐點名稱）` | 不設 UNIQUE（FR 允許同店同名） |
| `calories` | `NUMERIC(7,2)` | `NOT NULL`, `CHECK >= 0` | ✅ `calories` | **不加單位後綴**，逐字沿用契約 |
| `protein_g` | `NUMERIC(6,2)` | `NOT NULL`, `CHECK >= 0` | ✅ `protein_g` | |
| `carbs_g` | `NUMERIC(6,2)` | `NOT NULL`, `CHECK >= 0` | ✅ `carbs_g` | |
| `fat_g` | `NUMERIC(6,2)` | `NOT NULL`, `CHECK >= 0` | ✅ `fat_g` | |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `server_default now()` | ✅ `created_at` | **2026-08-04 契約新增**，與 `stores` 一致 |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, `server_default now()`, `onupdate` | ✅ `updated_at` | 同上 |

**欄位數 9，與更新後的契約完全一致，無增減。**

### 約束

```sql
CONSTRAINT ck_menu_items_calories CHECK (calories  >= 0)
CONSTRAINT ck_menu_items_protein  CHECK (protein_g >= 0)
CONSTRAINT ck_menu_items_carbs    CHECK (carbs_g   >= 0)
CONSTRAINT ck_menu_items_fat      CHECK (fat_g     >= 0)
FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE
```

`>= 0` 而非 `> 0`：FR-032 明確允許 0（零卡飲料、無脂餐點）。

### 索引

```sql
CREATE INDEX ix_menu_items_store ON menu_items (store_id);
```

**這一條要建。** 與 `stores` 不同，`menu_items` 的主要查詢型態是「取某店家底下的所有餐點」（FR-033，以及第二輪的餐點瀏覽），是明確的外鍵查詢。第一輪的 `meal_items` 也建了對應的 `ix_meal_items_record`，慣例一致。

### 驗證規則（應用層）

| 規則 | 來源 | 錯誤碼 |
|------|------|--------|
| `name` 非空白字串 | FR-032 | `VALIDATION_ERROR` |
| 四項數值皆為非負數字 | FR-032 | `VALIDATION_ERROR` |
| 所屬店家存在 | FR-035 | `NOT_FOUND` |
| 目標餐點存在 | FR-030 | `NOT_FOUND` |

---

## 關聯

```text
users ──(無關聯)── stores ──1:N（ON DELETE CASCADE）── menu_items

food_nutrition_references ──(無任何關聯)── stores / menu_items
meal_items                ──(無任何關聯)── stores / menu_items
```

- `stores` 與 `users` **不建立關聯**：本輪不記錄「哪位管理員建立了這家店」（操作稽核屬範圍外，見 spec「本輪範圍界線」）。日後若要加，是新增欄位，屬契約變更。
- ORM 端：`Store.menu_items` 設 `cascade="all, delete-orphan"` 與 `passive_deletes=True`，讓刪除由資料庫執行而非逐筆載入。

---

## 憲章原則 V 稽核（資料表分離）

本節將原樣寫入 migration 的 docstring，沿用第一輪 [20260803_0001_initial_schema.py](../../backend/alembic/versions/20260803_0001_initial_schema.py) 建立的慣例。

**檢查日期**：2026-08-04

1. **本 migration 建立的資料表共 2 張**：`stores`、`menu_items`。兩者皆屬「特定店家／餐點之營養值」體系。

2. **出向外鍵檢查**：
   - `stores`：無出向外鍵。
   - `menu_items`：僅 `store_id → stores.id`（同體系內部）。
   - **兩張表皆未指向 `food_nutrition_references`、`meal_items` 或任何第一輪的營養／紀錄資料表。**

3. **入向外鍵檢查**：第一輪的 6 張表無任何一張指向 `stores` 或 `menu_items`（本 migration 不修改既有表）。

4. **未以型別／分類欄位在單一表內混存兩類營養資料**：`menu_items` 只存店家餐點；通用食物營養值仍獨立存於 `food_nutrition_references`，兩者的寫入來源與查詢路徑完全分離。

5. **數值不互相參照**：即使 `menu_items.name` 與 `food_nutrition_references.name` 字面相同（例如兩邊都有「滷肉飯」），系統**不查詢、不比對、不同步、不以其一覆寫另一**（FR-041）。

**結論：符合憲章原則 V。**

---

## 第一輪既有資料表對照（確認未受影響）

| 資料表 | 本輪是否變更 |
|--------|------------|
| `users` | 結構不變，僅啟用既有 `role` 欄位的語意 |
| `health_profiles` | 不變 |
| `food_nutrition_references` | 不變 |
| `meal_records` | 不變 |
| `meal_items` | 不變 |
| `recognition_jobs` | 不變 |

本輪 migration 的 `upgrade()` 只有 `create_table` 與 `create_index`，**不含任何 `alter_table`**，故對第一輪資料表零風險（FR-043）。
