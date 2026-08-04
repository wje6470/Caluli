# Quickstart: 管理員角色與店家／餐點後台（第三輪）

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-04

本文件說明如何設定、指派管理員、以及驗證本輪功能是否正確運作。**不含實作程式碼**——實作細節屬 `tasks.md` 與實作階段。

---

## 1. 新增的環境變數

本輪只新增**一個**後端環境變數，前端無新增。

| 變數 | 位置 | 格式 | 預設 |
|------|------|------|------|
| `ADMIN_LINE_USER_IDS` | `backend/.env` | 半形逗號分隔的 LINE user ID | 空字串（＝無人是管理員） |

```bash
# backend/.env
ADMIN_LINE_USER_IDS=U1234567890abcdef1234567890abcdef,Uabcdef1234567890abcdef1234567890
```

**注意事項**：

- 格式是**逗號分隔的純字串，不是 JSON 陣列**（理由見 [research R-04](./research.md#r-04管理員名單的環境變數格式)）。逗號後可有空白，會自動去除。
- 留空或未設定時，系統正常啟動，所有使用者皆為一般使用者，後台無人可進入（FR-008）。**不會退回成「全體開放」。**
- 這個值決定誰能改動線上店家資料，正式環境請以部署平台的加密環境變數設定（Vercel 環境變數面板 / 容器 secret），**不要提交進版控**。

---

## 2. 指派第一位管理員

### 2.1 取得自己的 LINE user ID

LINE user ID 是形如 `U` 開頭的 33 字元字串，**不是** LINE 顯示名稱或 LINE ID（@開頭那個）。三種取得方式：

1. **從資料庫查（最可靠）**——先用該 LINE 帳號正常登入一次服務，然後查：

   ```sql
   SELECT line_user_id, display_name, role FROM users ORDER BY created_at DESC LIMIT 5;
   ```

2. 從後端登入時的日誌查看（若有開啟對應日誌）。
3. LINE Developers Console 的 channel 使用者列表。

### 2.2 寫入名單並重新啟動

```bash
# 1. 把 line_user_id 加進 backend/.env 的 ADMIN_LINE_USER_IDS
# 2. 重啟後端（設定以 lru_cache 快取，不重啟不會生效）
```

### 2.3 重新登入使該身分生效

**必須重新登入一次**——角色核對發生在登入流程中（[research R-03](./research.md#r-03管理員指派的實作方式)）。已持有的舊 token 不會自動升級。

登入後即可存取 `/admin`。

---

## 3. 撤銷管理員身分

> ⚠️ **順序很重要。** 因為登入時會依名單**雙向同步**角色，只改資料庫是無效的——下次登入會被名單復原。

### 標準流程（下次登入生效）

1. 從 `ADMIN_LINE_USER_IDS` 移除該 ID。
2. 重啟後端。
3. 該使用者下次登入時自動降為一般使用者。

### 需要立即生效時（雙步驟，缺一不可）

1. **先**從 `ADMIN_LINE_USER_IDS` 移除該 ID 並重啟後端。
2. **再**直接改資料庫，讓既有 token 立刻失去管理端存取能力：

   ```sql
   UPDATE users SET role = 'user' WHERE line_user_id = 'U....';
   ```

   權限一律即時查資料庫（[deps.py:44](../../backend/app/core/deps.py#L44)），所以這一步立刻生效，不需等 token 過期。

**若只做第 2 步而沒做第 1 步，該使用者下次登入就會恢復管理員身分。**

> 📌 同理，**直接在資料庫把 role 改成 `admin` 是無效的**——下次登入會被名單降回 `user`。授予管理員一律走名單。

---

## 4. 資料庫 migration

```bash
cd backend
alembic upgrade head
```

預期會執行 `20260804_0002_stores_menu_items`，建立 `stores` 與 `menu_items` 兩張表。

驗證：

```sql
\d stores
\d menu_items
```

應可看到 `stores` 的 3 條 CHECK 約束（座標成對、緯度範圍、經度範圍）與 `menu_items` 的 `store_id` 外鍵標註 `ON DELETE CASCADE`。

> ⚠️ 若同時在處理第二輪分支，請先看 [plan.md](./plan.md) 的「與第二輪分支的合併風險」——兩邊都建表會導致合併後 migration 失敗。

---

## 5. 執行測試

```bash
cd backend

# 全部（整合測試需要 Docker 或 TEST_DATABASE_URL）
pytest

# 只跑不需要資料庫的權限與名單邏輯
pytest tests/unit/

# 只跑本輪的管理端測試
pytest tests/unit/test_admin_roles.py tests/integration/test_admin_access_control.py tests/integration/test_admin_stores.py
```

Docker 不可用且未設 `TEST_DATABASE_URL` 時，整合測試會自動 skip，單元測試仍會執行（既有 conftest 行為）。

---

## 6. 驗證情境

以下 6 項對應 spec 的驗收標準，建議依序執行。

### 驗證 1 — 管理員可進入後台（US1）

**前置**：LINE 帳號已加入 `ADMIN_LINE_USER_IDS` 並重新登入。

| 步驟 | 預期 |
|------|------|
| 瀏覽器開啟 `/admin` | 看到店家清單頁（初次為空狀態） |
| 呼叫 `GET /api/v1/admin/me` | 200，`role: "admin"` |

### 驗證 2 — 一般使用者看不到任何後台入口（FR-017、SC-003）

**前置**：一個**不在**名單中的 LINE 帳號，已登入。

| 步驟 | 預期 |
|------|------|
| 瀏覽主要頁面（dashboard / capture / trends / profile） | 畫面上**沒有任何**指向 `/admin` 的連結或選單項目 |
| 直接在網址列輸入 `/admin` | 被導離至 `/dashboard`；**過程中不得閃現任何後台表格、欄位名稱或功能標題** |

### 驗證 3 — 一般使用者呼叫管理端 API 一律被拒（憲章必測情境、SC-001、SC-002）

**前置**：一般使用者的有效 token。

對**全部 10 支管理端端點**各發一次請求：

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

| 檢查項 | 預期 |
|--------|------|
| HTTP 狀態 | 全部 **403** |
| 回應 body | 全部**逐字相同**：`{"error":{"code":"FORBIDDEN","message":"沒有執行此操作的權限。","retryable":false}}` |
| 回應內容 | 不含端點用途、欄位名稱、內部路徑或任何後台功能線索 |
| 資料變更 | 寫入類請求（POST/PATCH/DELETE）執行後，資料庫**無任何變更** |
| 不帶 token 時 | 全部 **401**（而非 403） |

> 這是憲章原則 IV 明列的必測情境，也是本輪最重要的一項驗證。

### 驗證 4 — 店家 CRUD 與座標規則（US2）

| 步驟 | 預期 |
|------|------|
| 新增店家，只填名稱與地址 | 201 建立成功；清單中該筆**明確標示未設定座標**，並提示不會出現在附近店家推薦中 |
| 新增店家，名稱留空 | 422，訊息指出名稱必填；**不建立任何資料** |
| 新增店家，只填緯度不填經度 | 422，要求兩者同時填寫或同時留空 |
| 新增店家，緯度填 `91` | 422，指出正確範圍 |
| 新增店家，名稱與既有店家相同、地址不同 | 201 建立成功（連鎖分店允許同名） |
| 為未設座標的店家補上經緯度 | 200；清單中的未設定座標標示消失 |
| 編輯一家已被刪除的店家 | 404「找不到指定的資料。」 |

### 驗證 5 — 餐點 CRUD（US3）

| 步驟 | 預期 |
|------|------|
| 於某店家底下新增 3 道餐點 | 201 ×3；該店家餐點清單顯示 3 筆，**不含其他店家的餐點** |
| 新增餐點，熱量填 `-1` | 422，指出數值不得為負 |
| 新增餐點，熱量填 `0` | 201 成功（允許零卡） |
| 修改 A 店某餐點的熱量 | A 店該筆更新；B 店**同名餐點的數值不變** |
| 於不存在的店家底下新增餐點 | 404；**不產生無所屬店家的餐點** |
| 進入沒有餐點的店家 | 顯示空狀態與新增操作，非空白畫面或錯誤 |

### 驗證 6 — 刪除店家的連帶刪除（US4、SC-007、SC-008）

**前置**：一家底下有 3 道餐點的店家。

| 步驟 | 預期 |
|------|------|
| 點擊刪除 | 出現二次確認，**明確告知將一併刪除 3 道餐點** |
| 選擇取消 | 店家與 3 道餐點**皆保持原狀**，資料變更為 0 筆 |
| 再次點擊刪除並確認 | 204；店家自清單消失 |
| 查詢殘留餐點 | `SELECT count(*) FROM menu_items WHERE store_id = '<已刪除的 id>'` → **0** |
| 刪除沒有餐點的店家 | 仍要求二次確認，但提示說明沒有餐點會被一併刪除 |

---

## 7. 本輪不驗證的項目（屬第二輪）

以下屬 `feature/round2-restaurant` 範圍，本輪不實作也不驗證：

- 使用者端的店家清單查詢與定位權限請求
- 距離計算與「最近 10 家」排序
- 未設座標店家在距離排序中被排除的**讀取端**行為

本輪只保證**寫入端**產生的資料符合共用契約與其語意（座標可為 null 且必成對、刪除後無殘留餐點）。兩端的行為對齊表見 [spec.md](./spec.md) 的「與第二輪的介面約定」。
