# Data Model: 拍照飲食紀錄 MVP（第一輪）

**Date**: 2026-08-03 | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

資料庫：PostgreSQL 16。所有資料表使用 UUID 主鍵（`gen_random_uuid()`，需 `pgcrypto`），時間欄位一律 `TIMESTAMPTZ` 存 UTC。

## 資料表總覽

```text
users ──1:1── health_profiles
  │
  ├──1:N── meal_records ──1:N── meal_items ──N:1(nullable)── food_nutrition_references
  │                                                                    │
  └──1:N── recognition_jobs ───────────────────────────────────────────┘
                                                            （僅邏輯關聯，不設外鍵）

food_nutrition_references  ← 獨立資料集，與未來的店家／餐點資料表【無任何外鍵或共用】
```

> **憲章原則 V 落實點**：`food_nutrition_references` 是「拍照辨識用之通用食物營養對照表」。第二輪的「特定店家／餐點營養值」將是另一組完全獨立的資料表，兩者之間 **不得** 建立外鍵、不得共用資料表、不得以 type 欄位混存。本輪的 migration 不得建立任何店家／餐點相關資料表。

---

## users

服務使用者，以 LINE 身分識別。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | 內部識別碼，對外 API 一律使用此值 |
| `line_user_id` | TEXT | NOT NULL, UNIQUE | LINE ID Token 的 `sub`。不論來自 LIFF 或網頁 OAuth 皆寫入同一欄位（憲章原則 I） |
| `display_name` | TEXT | NULL | LINE 顯示名稱，登入時更新 |
| `picture_url` | TEXT | NULL | LINE 頭像 URL |
| `role` | TEXT | NOT NULL, default `'user'`, CHECK IN (`'user'`,`'admin'`) | 本輪一律為 `user`；為憲章原則 IV 的權限層預留（見 [research.md](./research.md) R-14） |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |

**索引**：`UNIQUE (line_user_id)`

**驗證規則**

- `line_user_id` 由 LINE 憑證驗證流程取得，不接受客戶端直接指定。
- 本輪 **不提供** 任何將 `role` 改為 `admin` 的 API；如需指派管理員，於資料庫直接操作。

**對應需求**：FR-001、FR-006、FR-007、FR-044

---

## health_profiles

使用者的生理基本資料與由此推導的每日目標。與 `users` 為 1:1。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | NOT NULL, UNIQUE, FK → `users(id)` ON DELETE CASCADE | 1:1 由 UNIQUE 保證 |
| `gender` | TEXT | NOT NULL, CHECK IN (`'male'`,`'female'`) | BMR 公式所需（OQ-7） |
| `age_years` | SMALLINT | NOT NULL, CHECK 15–90 | 儲存歲數而非出生日期（OQ-8） |
| `height_cm` | NUMERIC(5,1) | NOT NULL, CHECK 100.0–250.0 | |
| `weight_kg` | NUMERIC(5,1) | NOT NULL, CHECK 25.0–300.0 | |
| `activity_level` | TEXT | NOT NULL, CHECK IN (`'low'`,`'moderate'`,`'high'`) | 係數 1.2 / 1.45 / 1.75 |
| `bmr_kcal` | NUMERIC(7,2) | NOT NULL | 後端計算後寫入，不接受客戶端提供 |
| `tdee_kcal` | NUMERIC(7,2) | NOT NULL | 即每日建議熱量 |
| `target_protein_g` | NUMERIC(6,1) | NOT NULL | |
| `target_carbs_g` | NUMERIC(6,1) | NOT NULL | |
| `target_fat_g` | NUMERIC(6,1) | NOT NULL | |
| `computed_at` | TIMESTAMPTZ | NOT NULL, default `now()` | 目標值最後一次重算的時間 |
| `created_at` / `updated_at` | TIMESTAMPTZ | NOT NULL | |

**驗證規則**

- CHECK 範圍即 FR-014 的合理生理範圍，後端 Pydantic schema 需與 DB CHECK 一致（雙層驗證，錯誤訊息由 API 層產生）。
- `bmr_kcal`、`tdee_kcal` 與三項目標值 **一律由後端 `services/targets.py` 計算**（R-13），API 忽略客戶端傳入的這些欄位。
- 使用者不存在 `health_profiles` 記錄 = 尚未完成首次建檔 → API 於 `GET /api/v1/me` 回傳 `profile_completed: false`，前端據此導向 onboarding（FR-013）。

**狀態轉換**

```text
（無 profile）──POST/PUT /me/profile──▶（profile 已建立，目標已計算）
                                              │
                                              └──PUT /me/profile──▶（重算目標，computed_at 更新）
                                                   ⚠ 不影響任何既有 meal_items（FR-016）
```

**對應需求**：FR-009〜FR-016

---

## food_nutrition_references

通用食物營養對照表。**獨立資料集**。

**2026-08-04 更新**：辨識服務改為串接外部「台灣小吃辨識 API」後（見 [research.md](./research.md) R-16），此表**不再是辨識結果換算營養值的必經路徑**——外部服務直接回傳該品項的熱量與三大營養素。此表現在的用途改為供 `GET /foods/search`（FR-037 使用者手動搜尋修正食物名稱）使用，與辨識流程解耦。表結構本身不變，`model_label` 欄位保留供未來其他辨識來源沿用，但本輪辨識路徑不再以此欄位查表。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `model_label` | TEXT | NOT NULL, UNIQUE | 對應 HF 分類模型輸出的類別標籤，是辨識結果查表的鍵 |
| `name` | TEXT | NOT NULL | 顯示用食物名稱（繁體中文），例如「滷肉飯」 |
| `name_normalized` | TEXT | NOT NULL | 供搜尋比對用的正規化名稱（去空白、統一大小寫） |
| `calories_kcal_per_100g` | NUMERIC(7,2) | NOT NULL, CHECK ≥ 0 | |
| `protein_g_per_100g` | NUMERIC(6,2) | NOT NULL, CHECK ≥ 0 | |
| `carbs_g_per_100g` | NUMERIC(6,2) | NOT NULL, CHECK ≥ 0 | |
| `fat_g_per_100g` | NUMERIC(6,2) | NOT NULL, CHECK ≥ 0 | |
| `default_portion_grams` | NUMERIC(6,1) | NOT NULL, CHECK > 0 | **系統設定的預設份量**（例：滷肉飯 250），非模型輸出（FR-022） |
| `is_active` | BOOLEAN | NOT NULL, default `true` | 停用的項目不再出現於新辨識結果，但既有紀錄不受影響 |
| `source` | TEXT | NULL | 資料來源註記，供稽核（OQ-2） |
| `created_at` / `updated_at` | TIMESTAMPTZ | NOT NULL | |

**索引**：`UNIQUE (model_label)`、`INDEX (name_normalized)`（供 `GET /foods/search` 使用）

**驗證規則**

- `name_normalized` 需可涵蓋常見的使用者手動修正搜尋情境；查無資料時該品項走 FR-037 的「無法自動換算」路徑。
- `model_label` 為既有欄位，本輪辨識路徑不使用，保留供未來可能的其他辨識來源沿用；不因此輪不使用而移除欄位或放寬 UNIQUE 約束。
- 本輪透過 seed 腳本匯入，**不提供維護 API**（管理員後台屬第二輪）。

**⚠️ 禁止事項**：此表不得與任何店家／餐點資料表建立外鍵、不得被後續輪次改造為共用表。

**對應需求**：FR-021、FR-022、FR-037、FR-056

---

## meal_records

一次記帳（一筆飲食紀錄），對應一次拍照辨識的確認結果。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | NOT NULL, FK → `users(id)` ON DELETE CASCADE | |
| `record_date` | DATE | NOT NULL | 歸屬日期，依 `Asia/Taipei` 由 `captured_at` 換算後物化（R-12、FR-040） |
| `meal_type` | TEXT | NOT NULL, CHECK IN (`'breakfast'`,`'lunch'`,`'dinner'`,`'snack'`) | 依當下時間給預設值，使用者可改（FR-038） |
| `captured_at` | TIMESTAMPTZ | NOT NULL | 拍攝／建立時間 |
| `photo_path` | TEXT | NULL | 相對於 `PHOTO_STORAGE_ROOT`；無照片（純手動修正情境）時為 NULL |
| `recognition_job_id` | UUID | NULL | 來源辨識工作，供追溯；**不設外鍵**以免刪除 job 時牽動紀錄 |
| `note` | TEXT | NULL | 預留 |
| `created_at` / `updated_at` | TIMESTAMPTZ | NOT NULL | |

**索引**：`INDEX (user_id, record_date)` ← 儀表板與趨勢查詢的主要路徑

**設計註記**：不儲存合計欄位。合計由 `meal_items` 即時 `SUM()` 得出——本輪規模（25 人 × 每日約 5 筆）下聚合成本可忽略，而省下「編輯品項後合計未同步」這類一致性缺陷。若日後規模成長，可加物化的每日彙總表而不需改動現有欄位。

**對應需求**：FR-039〜FR-044

---

## meal_items

飲食紀錄中的單一食物品項。**營養值為寫入當下的快照**。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK | |
| `meal_record_id` | UUID | NOT NULL, FK → `meal_records(id)` ON DELETE CASCADE | |
| `food_reference_id` | UUID | NULL, FK → `food_nutrition_references(id)` ON DELETE SET NULL | 僅供來源追溯；NULL = 使用者自行輸入的品項，或來自辨識流程的品項（本輪辨識服務不再經由此表換算，見 R-16，故辨識產生的品項一律為 NULL）（FR-037） |
| `display_order` | SMALLINT | NOT NULL, default 0 | 維持辨識結果的呈現順序 |
| `food_name` | TEXT | NOT NULL | 名稱快照（使用者可能已修改） |
| `default_portion_grams` | NUMERIC(6,1) | NULL | 系統原本套用的預設份量，供分析「使用者調整幅度」 |
| `portion_grams` | NUMERIC(6,1) | NOT NULL, CHECK > 0 AND ≤ 5000 | 使用者確認後的份量（FR-034） |
| `calories_kcal_per_100g` | NUMERIC(7,2) | NOT NULL, CHECK ≥ 0 | 每 100g 快照 |
| `protein_g_per_100g` | NUMERIC(6,2) | NOT NULL, CHECK ≥ 0 | 每 100g 快照 |
| `carbs_g_per_100g` | NUMERIC(6,2) | NOT NULL, CHECK ≥ 0 | 每 100g 快照 |
| `fat_g_per_100g` | NUMERIC(6,2) | NOT NULL, CHECK ≥ 0 | 每 100g 快照 |
| `calories_kcal` | NUMERIC(8,2) | NOT NULL, CHECK ≥ 0 | 換算結果，後端驗算後寫入 |
| `protein_g` | NUMERIC(7,2) | NOT NULL, CHECK ≥ 0 | 換算結果 |
| `carbs_g` | NUMERIC(7,2) | NOT NULL, CHECK ≥ 0 | 換算結果 |
| `fat_g` | NUMERIC(7,2) | NOT NULL, CHECK ≥ 0 | 換算結果 |
| `recognition_confidence` | NUMERIC(4,3) | NULL, CHECK 0–1 | 模型信心度；使用者自行輸入時為 NULL |
| `is_user_modified` | BOOLEAN | NOT NULL, default `false` | 名稱、份量或營養值曾被使用者改動 |
| `created_at` / `updated_at` | TIMESTAMPTZ | NOT NULL | |

**索引**：`INDEX (meal_record_id)`

**驗證規則（後端寫入前）**

```text
expected = per_100g_value × portion_grams / 100
若 |客戶端送出值 − expected| > max(0.5, expected × 0.01)
   → 以 expected 為準寫入（客戶端數值不採信，R-09）
```

**快照理由**：日後修正 `food_nutrition_references` 的數值 **不得** 追溯改變已儲存的歷史紀錄與趨勢圖（R-11）。因此 `food_reference_id` 只是弱關聯，刪除對照項目時設為 NULL 而非串連刪除。

**對應需求**：FR-023、FR-031〜FR-037、FR-039、FR-042

---

## recognition_jobs

一次辨識請求的生命週期紀錄。**這是同步／非同步遷移的接縫**（R-07）。

| 欄位 | 型別 | 約束 | 說明 |
|---|---|---|---|
| `id` | UUID | PK | 對外即 `recognition_id` |
| `user_id` | UUID | NOT NULL, FK → `users(id)` ON DELETE CASCADE | |
| `status` | TEXT | NOT NULL, CHECK IN (`'processing'`,`'completed'`,`'failed'`) | 本輪同步實作下，`processing` 僅短暫存在於請求處理期間 |
| `photo_path` | TEXT | NOT NULL | 重試時重用，使用者不需重新上傳（FR-028） |
| `requested_at` | TIMESTAMPTZ | NOT NULL, default `now()` | |
| `completed_at` | TIMESTAMPTZ | NULL | |
| `duration_ms` | INTEGER | NULL | 供 OQ-1／OQ-4 的實測依據 |
| `item_count` | SMALLINT | NULL | 0 代表未偵測到食物（非錯誤） |
| `service_message` | TEXT | NULL | 空結果時顯示於引導畫面的說明文字；外部辨識服務不提供此欄位，由後端 adapter 合成固定文案寫入（見 [contracts/recognition-service.md](./contracts/recognition-service.md)） |
| `error_code` | TEXT | NULL | `TIMEOUT` / `UNAVAILABLE` / `BAD_RESPONSE` |
| `retry_count` | SMALLINT | NOT NULL, default 0 | 使用者顯式重試次數 |
| `raw_response` | JSONB | NULL | 辨識服務原始回應（`{items: [...]}`，欄位含 `estimated_weight_g`／絕對營養值／`bbox: {x1,y1,x2,y2}`），供除錯與稽核 |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

**索引**：`INDEX (user_id, requested_at DESC)`

**狀態轉換**

```text
        POST /recognitions
                │
                ▼
          [processing] ──成功(items ≥ 0)──▶ [completed]  ← items:[] 也是 completed
                │
                └──逾時／5xx／解析失敗──▶ [failed] ──POST /{id}/retry──▶ [processing]
```

**設計註記**：`item_count = 0` 且 `status = completed` 即「未偵測到食物」——這是**成功**狀態，前端據此顯示引導畫面而非錯誤畫面（FR-027）。此區分是本輪最容易誤判的分支，資料模型上刻意讓它落在 `completed` 而非 `failed`。

**對應需求**：FR-020、FR-025〜FR-030

---

## 查詢路徑

| 用途 | 查詢 | 使用索引 |
|---|---|---|
| 儀表板（單日） | `meal_records` JOIN `meal_items` WHERE `user_id` AND `record_date` = ? | `(user_id, record_date)` |
| 趨勢（7/14/30 天） | 同上，`record_date BETWEEN ? AND ?`，依 `record_date` 分組聚合 | `(user_id, record_date)` |
| 食物名稱搜尋（FR-037 手動修正） | `food_nutrition_references` WHERE `name_normalized ILIKE ?` AND `is_active` | `(name_normalized)` |

趨勢查詢中「沒有紀錄的日期以零呈現」（FR-054）由**後端補齊日期序列**，不依賴資料庫產生空列——查詢回傳有資料的日期，服務層以完整日期區間填 0。

## 資料隔離

所有涉及使用者資料的查詢一律帶 `user_id = current_user.id` 條件，不存在「先查全部再過濾」的實作路徑。跨使用者存取一律回 `404 NOT_FOUND`（不回 403，避免洩漏資源是否存在）。此規則涵蓋 `meal_records`、`meal_items`、`recognition_jobs` 與照片檔案存取端點（FR-044、SC-009）。
