# Phase 0 Research: 管理員角色與店家／餐點後台（第三輪）

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-04

本輪絕大多數技術選型已由第一輪既有實作與專案憲章鎖定，故研究重點不在「用什麼技術」，而在「如何在既有結構上正確接入，且不破壞與第二輪的共用契約」。

---

## R-01：管理端 API 的路由前綴

**Decision**: 管理端端點掛在 `/api/v1/admin/*`，而非 plan brief 舉例的 `/api/admin/*`。

**Rationale**:

1. 前端的 `NEXT_PUBLIC_API_BASE_URL` 已經是 `http://localhost:8000/api/v1`（見 [frontend/.env.local.example](../../frontend/.env.local.example)），所有呼叫皆為 `${apiBaseUrl}${path}`。若管理端另立 `/api/admin`，前端必須引入**第二個 base URL 環境變數**，或在 client 內為管理端寫特例分支——兩者都會讓「所有客戶端呼叫同一組後端」的單純結構出現裂縫。
2. 既有 API 已採 `/api/v1` 版本化。管理端若脫離版本前綴，日後版本演進時管理端會沒有版本可依循。
3. **關鍵**：URL 前綴不是安全邊界。隔離的實質保證來自 R-02 的 router 層依賴掛載，前綴只是可讀性上的分組。brief 用「例如」提出 `/api/admin/*`，其意圖是「管理端要有獨立的路由群組並統一套用權限檢查」——這個意圖由 `/api/v1/admin` 完整達成。

**Alternatives considered**:

- `/api/admin/*`（brief 的舉例）：需要前端第二個 base URL；且與既有版本化慣例不一致。
- 獨立的 FastAPI 子應用（`app.mount("/admin", admin_app)`）：可做到更徹底的隔離，但會分裂錯誤處理器、CORS 設定與 OpenAPI 文件，違反憲章原則 III「單一後端、API 契約一致」，成本遠大於收益。

---

## R-02：權限檢查層的掛載方式

**Decision**: 在 router 建構時統一掛載，不在各端點的函式簽章逐一宣告：

```python
router = APIRouter(
    prefix="/admin/stores",
    tags=["admin"],
    dependencies=[Depends(require_admin)],   # ← 整個 router 的每一支端點都會經過
)
```

第一輪既有的 `require_admin()`（[deps.py:53](../../backend/app/core/deps.py#L53)）**完全不需修改**，直接使用。

**Rationale**:

1. 憲章「架構約束」明文要求：管理員權限檢查必須是可被單獨測試的獨立元件，**不得在各端點內重複手寫判斷邏輯**。router 層掛載是唯一能讓「新增端點時不可能忘記加權限」的做法。
2. 若採 `def endpoint(admin: AdminUser)` 的逐端點寫法，漏寫一支就是一個完全敞開的管理端點，且這種疏漏在 code review 中極易滑過。router 層掛載把「安全」變成預設值而非紀律。
3. `dependencies=[...]` 的依賴不會把回傳值注入端點函式。管理端 CRUD 本身不需要知道「是哪位管理員」（本輪不做操作稽核紀錄），故不需要注入。日後若要記錄操作者，再於個別端點額外加 `admin: AdminUser` 參數即可，兩者可並存。

**Alternatives considered**:

- 逐端點 `admin: AdminUser` 參數注入：可取得管理員身分，但有漏寫風險，且違反憲章的「不得重複手寫」。
- ASGI middleware 依路徑前綴攔截：middleware 早於路由解析執行，取不到 DB session 與已解析的使用者，需重造一套 token 解析邏輯，會製造出第二套驗證實作——直接違反憲章原則 I。

---

## R-03：管理員指派的實作方式

**Decision**: 部署層級的環境變數持有 LINE 使用者 ID 名單，於 `upsert_user()` 內核對並**雙向同步** `users.role`。

```
登入（LIFF 或網頁）
  → verify_line_identity()      既有，不改
  → upsert_user()               既有，於此處插入一行角色核對
      ├─ line_user_id ∈ 名單  → role = 'admin'
      └─ line_user_id ∉ 名單  → role = 'user'
  → issue_session()             既有，不改
```

**Rationale**:

1. `upsert_user()` 是 LIFF 與一般網頁**唯一的匯流點**（[line_auth.py:107](../../backend/app/services/line_auth.py#L107) 的模組註解已明示此設計）。在此處核對，一次涵蓋兩個入口與未來的原生客戶端，不需要為任何入口寫特例——符合憲章原則 I。
2. 核對發生在身分驗證**之後**：`line_user_id` 來自 LINE 官方驗證過的 ID Token `sub`，不是客戶端可自行宣告的值。使用者無法藉由偽造請求把自己放進名單。
3. **名單是單一真實來源，故必須雙向同步**：只升不降會讓「從名單移除」無效（使用者的 role 永遠停在 admin）。雙向同步使名單成為宣告式設定——名單內容即系統的實際狀態。
4. 系統中不存在任何寫入 `role` 的 API 端點。`PUT /me/profile` 只接受 `HealthProfileInput`，其欄位白名單不含 role（[schemas/profile.py](../../backend/app/schemas/profile.py)），故無法透過 mass assignment 提權。

**安全性考量（brief 明確要求說明）**:

| 攻擊面 | 是否成立 | 原因 |
|--------|---------|------|
| 使用者偽造請求把自己設為管理員 | ❌ 不成立 | 無任何 API 可寫入 role；role 僅由後端依名單設定 |
| 偽造 `line_user_id` 混入名單 | ❌ 不成立 | `line_user_id` 取自 LINE 官方 verify endpoint 回傳的 `sub`，非客戶端輸入 |
| 竄改前端狀態偽裝管理員 | ❌ 不成立 | 前端判斷僅影響畫面；每一支管理端 API 都在後端獨立驗證（R-02） |
| 竄改 JWT 內容夾帶 role | ❌ 不成立 | token 內只有 user_id，權限一律即時查 DB（[deps.py:44](../../backend/app/core/deps.py#L44)），token 中沒有 role 可竄改 |
| 名單環境變數外洩 | ⚠️ 影響有限 | 洩漏的是「誰是管理員」，攻擊者仍需通過該 LINE 帳號的 LINE Login 才能取得身分 |
| 舊 token 在角色撤銷後仍可用 | ⚠️ 部分成立 | 見 OQ-3：DB 的 role 一改即刻生效，但若名單未同步移除，下次登入會復原 |

**⚠️ 營運上必須知道的一點**：因為是雙向同步，**直接改資料庫授予 admin 是無效的**（下次登入會被降回 user）。資料庫直改僅可作為「緊急撤銷」的即時手段，且撤銷後**必須同步把該帳號移出名單**，否則下次登入即復原。完整流程見 [quickstart.md](./quickstart.md)。

**Alternatives considered**:

- **僅在資料庫手動 UPDATE role**（第一輪 user.py 註解所設想的做法）：最省事，但沒有宣告式的名單，無法從設定看出「目前誰是管理員」，且部署到新環境時管理員會全部消失（資料是空的）。保留為緊急撤銷手段。
- **只有特定金鑰能呼叫的內部指派 API**（brief 舉例之一）：需要多維護一組金鑰、一支能寫 role 的端點，以及該端點的防護。**新增了一條在其他方案中根本不存在的提權路徑**，是三個方案中攻擊面最大的，故不採用。
- **只升不降的單向同步**：實作更簡單，但會讓移除名單完全失效，違反 FR-007。

---

## R-04：管理員名單的環境變數格式

**Decision**: 設定型別用 `str`，以半形逗號分隔，於 Settings 內以 property 解析為 `frozenset[str]`：

```python
admin_line_user_ids: str = ""          # "U1234...,U5678..."

@property
def admin_line_user_id_set(self) -> frozenset[str]:
    return frozenset(s.strip() for s in self.admin_line_user_ids.split(",") if s.strip())
```

**Rationale**:

1. pydantic-settings v2 對 `list[str]` 型別的欄位，會要求環境變數是 **JSON 格式**（`["U1","U2"]`）。引號在 `.env`、docker-compose、Vercel 環境變數面板中都容易被吃掉或轉義錯誤，是一個現成的踩雷點。逗號分隔的字串沒有這個問題。
2. 既有的 `cors_origins: list[str]` 雖是 list，但它有 `default_factory` 且實務上少從環境變數覆寫；管理員名單則是**必然要從環境變數設定**的，格式的易用性更關鍵。
3. 解析為 `frozenset` 讓核對是 O(1) 且不可變，避免任何位置意外修改名單。
4. `strip()` 容忍逗號後的空白與換行，減少設定時的低級錯誤。

**Alternatives considered**:

- `list[str]` + JSON 格式：與既有 `cors_origins` 一致，但引號轉義易錯。
- 獨立的名單檔案（JSON/YAML）：多一個部署產物，且 Vercel serverless 的檔案系統唯讀，反而更麻煩。

---

## R-05：拒絕回應用 403 還是 404（存在性洩漏的取捨）

**Decision**: 已登入的一般使用者存取管理端端點，一律回 **403 FORBIDDEN**，使用既有錯誤目錄中的通用訊息「沒有執行此操作的權限。」（[errors.py:25](../../backend/app/core/errors.py#L25)）。未登入者回 **401 UNAUTHORIZED**。

**Rationale**:

1. spec FR-014 與 US1 驗收情境 3 明確要求回「權限不足」，brief 的原文也是「應回傳權限錯誤」。
2. FR-015 要求「所有管理端功能的拒絕回應彼此一致，使呼叫方無法藉回應差異推測何者存在」——統一回同一個 403 與同一句訊息，完全滿足此點。既有的 `FORBIDDEN` 訊息本身不含任何功能語意，不透露這是店家管理、餐點管理或其他。
3. 401 與 403 的區分符合 FR-016：未攜帶憑證者得到的是「請重新登入」，不會因為「已登入才會看到 403」而推斷出權限體系的結構。

**已知殘留風險（明確記錄，不隱藏）**：

主應用有一條 catch-all 404 路由（[main.py:84](../../backend/app/main.py#L84)），未匹配的路徑回 404。因此一般使用者可藉由「403 = 路徑存在 / 404 = 路徑不存在」的差異，推知某個路徑底下有管理端功能。

**接受此殘留的理由**：spec 的 Assumptions 已明文採取此立場——「後台的存取入口不對一般使用者曝光；其網址本身不視為機密，安全性由後端權限檢查層保證，而非由網址的不可預測性保證」。攻擊者即使確知 `/api/v1/admin/stores` 存在，也無法取得任何資料或造成任何變更。以 404 偽裝換取的是「攻擊者需多猜一步」，代價則是違反 FR-014 的明文要求、且讓管理員自己遇到權限問題時收到誤導性的 404，難以排查。

**Alternatives considered**:

- 管理端一律回 404 偽裝不存在：存在性完全不洩漏，但違反 FR-014 明文，且管理員排查困難。
- 403 但延長回應時間以混淆：徒增複雜度，對 URL 列舉無實質防護。

---

## R-06：座標欄位的資料庫層設計

**Decision**: `latitude` / `longitude` 皆為 `NUMERIC(9,6)` 且 `nullable=True`，另加兩條 CHECK 約束：

```sql
CHECK ((latitude IS NULL) = (longitude IS NULL))                      -- 成對
CHECK (latitude  IS NULL OR (latitude  BETWEEN  -90 AND  90))         -- 緯度範圍
CHECK (longitude IS NULL OR (longitude BETWEEN -180 AND 180))         -- 經度範圍
```

**Rationale**:

1. 契約定義座標欄位存在但未定可空性；spec FR-021 已確認為選填，故 `nullable=True`。
2. `(latitude IS NULL) = (longitude IS NULL)` 是在 PostgreSQL 中表達「成對」最精簡的寫法（布林等值比較），讓 FR-022 成為**結構上不可能違反**的約束，而非只靠應用層驗證。
3. `NUMERIC(9,6)` 提供 6 位小數（約 0.1 公尺精度），對餐廳定位綽綽有餘，且與既有 model 慣用 `Numeric` 而非 float 的作風一致（避免浮點誤差）。
4. 雙層驗證沿用第一輪慣例（見 [schemas/profile.py](../../backend/app/schemas/profile.py) 的註解）：pydantic 層負責產生可讀的中文錯誤訊息，DB CHECK 負責兜底。

**與第二輪的交接**：讀取端遇到 `latitude IS NULL` 的店家時，不納入距離排序（FR-024）。此規則已寫入共用契約檔的「欄位語意補充」。

**Alternatives considered**:

- `FLOAT` / `DOUBLE PRECISION`：PostGIS 生態常用，但本專案不引入地理擴充（第二輪 brief 明示「不需要導入額外的地理資料庫工具」），且 `Numeric` 與既有慣例一致。
- 兩欄位都 NOT NULL：見 spec Assumptions，會逼出「隨便填一個座標」的更糟結果。

---

## R-07：`menu_items.store_id` 的 ON DELETE 規則

**Decision**: `ON DELETE CASCADE`。

```python
store_id: Mapped[uuid.UUID] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("stores.id", ondelete="CASCADE"),
    nullable=False,
)
```

ORM 端的 relationship 設 `cascade="all, delete-orphan"` 且 `passive_deletes=True`，讓刪除交由資料庫執行，不逐筆載入。

**Rationale（brief 明確要求說明選擇理由）**:

1. spec FR-037 已定案「刪除店家連帶刪除其餐點，且不得要求管理員先逐一刪除餐點」。`RESTRICT` 會直接違反此需求。
2. 餐點以 `store_id NOT NULL` 為必要歸屬，店家不存在時餐點無獨立意義，不存在「保留孤兒餐點」的正當情境。
3. **CASCADE 讓 FR-040「不得殘留指向已刪除店家的餐點」成為結構保證**。若改由應用層先刪餐點再刪店家，任何一次忘記、任何一次中途例外，都會留下孤兒資料；DB 層 cascade 則在交易語意上保證兩者同生共死。
4. 與第一輪既有慣例一致：`meal_items.meal_record_id` 同樣是 `ON DELETE CASCADE`（[meal_item.py:48](../../backend/app/db/models/meal_item.py#L48)），語意相同——子資料無法脫離父資料存在。

**與既有 `SET NULL` 用法的區辨**：第一輪的 `meal_items.food_reference_id` 用 `SET NULL`，因為那是**弱關聯**（僅供來源追溯，刪除對照表不該刪掉使用者的歷史紀錄）。本輪的 `store_id` 是**強歸屬**，兩者語意不同，不可比照。

**誤刪防護**：CASCADE 本身無法還原，故防護放在應用層——刪除前先查餐點數量，前端二次確認並告知數量（FR-038）。這是 spec 已定案的設計。

**Alternatives considered**:

- `ON DELETE RESTRICT`：資料更安全（有餐點時無法刪店家），但違反 FR-037，且會讓管理員為了刪一家店得先刪 30 道餐點。
- 不設 DB 層規則、由應用層處理：語意等同 CASCADE 但無結構保證，是三者中最容易產生孤兒資料的。

---

## R-08：刪除前如何取得「將一併刪除的餐點數量」

**Decision**: 店家清單端點 `GET /admin/stores` 於每筆店家附帶 `menu_item_count`，以單一 `LEFT OUTER JOIN + GROUP BY` 一次算出，前端無需額外請求。

**Rationale**:

1. FR-038 要求刪除確認提示中告知餐點數量。若另開一支 `GET /admin/stores/{id}/menu-items/count`，會在使用者按下刪除時多一次往返與一個載入狀態，對「精簡快速」的後台是不必要的複雜度。
2. 清單頁本來就該顯示每家店有幾道餐點（管理員需要這個資訊來判斷資料完整度），所以這個欄位不是為刪除而額外增加的負擔。
3. 店家數量為數十至數百筆，一次 JOIN 聚合的成本可忽略。

**Alternatives considered**:

- 刪除時才即時查詢數量：多一次往返；且「查完到按確認」之間仍可能變動，準確度並未提升。
- 由前端載入全部餐點後自行計數：需要 N+1 次請求，明顯更差。

---

## R-09：營養數值與座標的數值型別

**Decision**: 沿用第一輪的 `Numeric` 慣例——`calories`：`NUMERIC(7,2)`；`protein_g` / `carbs_g` / `fat_g`：`NUMERIC(6,2)`；四者皆 `NOT NULL` 且加 `CHECK (>= 0)`。

**Rationale**:

1. 與 [meal_item.py:29-36](../../backend/app/db/models/meal_item.py#L29) 的既有 CHECK 慣例完全一致（每個營養欄位一條 `>= 0` 約束，並具名 `ck_<table>_<column>`）。同一個 codebase 內兩套數值慣例會讓後續維護者困惑。
2. 營養數值涉及加總與顯示，`Numeric` 避免浮點累積誤差。
3. `>= 0` 而非 `> 0`：FR-032 明確允許 0（零卡飲料、無脂餐點）。

**契約對應**：共用契約僅列出欄位名稱（`calories`、`protein_g`…）未指定型別，此處的型別選擇不構成契約變更；但**欄位名稱逐字沿用契約，不加單位後綴**（例如不改成 `calories_kcal`），即使第一輪的 `meal_items` 用的是 `calories_kcal`。契約優先於內部命名一致性。

---

## R-10：前端後台的路由位置

**Decision**: 放在 `src/app/admin/`，**不放進既有的 `(app)` 路由群組**，並自建 `layout.tsx` 守衛。

**Rationale**:

1. **這是一個會直接讓功能不可用的陷阱**：`(app)/layout.tsx` 有一道「已登入但未建檔 → 強制導向 `/onboarding`」的守衛（[(app)/layout.tsx:41](../../frontend/src/app/(app)/layout.tsx#L41)）。管理員是內部人員，很可能從未填寫過身高體重等健康檔案。若後台放進 `(app)`，管理員一進後台就會被踢去 onboarding，永遠進不去。
2. `(app)` 的外框包含 `BottomNav` 與 `max-w-md` 的手機版寬度限制——後台是桌機表格介面，兩者都不適用。
3. 分開的 layout 讓「一般使用者的殼」與「後台的殼」互不影響，FR-017「一般使用者看不到任何後台入口」在結構上即成立：`BottomNav` 完全不需修改，也就不可能不小心露出後台連結。

**守衛設計**：`admin/layout.tsx` 呼叫 `GET /api/v1/admin/me`，403 或 401 即 `router.replace('/dashboard')`，且在確認為管理員之前**不渲染任何後台內容**（避免 FR-017 要求的「不得看到後台畫面骨架、欄位名稱或功能標題」）。

---

## R-11：前端如何判斷目前使用者是否為管理員

**Decision**: 新增一支極小的 `GET /api/v1/admin/me`，掛在同一個管理端 router 群組下。前端後台守衛呼叫它——成功即為管理員，403 即不是。**不在既有的 `UserOut` / `MeResponse` 加 `role` 欄位。**

**Rationale**:

1. FR-043 要求不修改第一輪既有 API 的行為。在 `UserOut` 加欄位雖是相容的擴充，但仍會改動既有契約與其快照測試，且會讓每一位一般使用者的 `/me` 回應都帶著角色資訊——沒有必要擴大暴露面。
2. 用「呼叫一支受保護的端點看它通不通過」來判斷權限，**與後端實際的授權判斷是同一條路徑**。相對地，若前端讀 `/me` 的 role 欄位自行判斷，就出現了第二套判斷邏輯，兩者可能不一致。
3. 這支端點同時是整個管理端 router 群組的健康檢查——它通過，代表權限層掛載正確。

**回應內容**：僅 `{ "user_id": ..., "display_name": ..., "role": "admin" }`，不含任何 LINE 憑證或名單資訊。

**Alternatives considered**:

- 在 `UserOut` 加 `role`：改動既有契約，且前端會出現與後端平行的判斷邏輯。
- 前端直接探測 `GET /admin/stores`：可行且不需新端點，但語意不清（守衛與資料載入混在一起），且守衛失敗時會浪費一次清單查詢。

---

## R-12：Migration 的版次與命名

**Decision**: 新增 `backend/alembic/versions/20260804_0002_stores_menu_items.py`，`revision = "0002"`，`down_revision = "0001"`。沿用第一輪的檔名格式（`YYYYMMDD_NNNN_描述`）與「在 docstring 內附憲章原則 V 稽核紀錄」的慣例。

**Rationale**: 第一輪的 [20260803_0001_initial_schema.py](../../backend/alembic/versions/20260803_0001_initial_schema.py) 在 docstring 中留了一段憲章原則 V 的稽核紀錄，明確記載「本 migration 沒有建立任何店家／餐點資料表」。本輪正是建立那兩張表的一輪，**必須在同樣的位置留下對應的稽核**，說明新表與 `food_nutrition_references` 之間確無任何關聯。維持這個慣例，讓稽核紀錄可以沿著 migration 鏈連續閱讀。

**⚠️ 合併風險**：見 [plan.md](./plan.md) 的「與第二輪分支的合併風險」（OQ-2）。

---

## R-13：後台介面的技術選擇

**Decision**: 原生 HTML `<table>` + `<form>`，沿用專案既有的 Tailwind class，**不引入任何 UI 元件庫、表格庫或表單庫**。編輯採同頁的簡單 modal（可沿用既有的 [Modal.tsx](../../frontend/src/components/ui/Modal.tsx)），資料存取沿用既有的 TanStack Query。

**Rationale**:

1. spec FR-045／FR-046 與 brief 都明確要求以精簡快速為原則，不投入視覺打磨、不比照原型風格、不做深色模式。
2. 引入 `react-table` 或元件庫會增加相依套件與打包體積，違反憲章原則 VI「在既有技術棧可達成需求時，禁止為單一功能引入平行的框架」。
3. 資料規模（數十至數百筆）不需要虛擬捲動、分頁或欄位排序等元件庫才划算的能力。
4. 沿用既有 `Modal.tsx` 與 TanStack Query，讓後台的錯誤處理與載入狀態行為與主產品一致，不必重造。

**明確不做**：深色模式、行動版版面、動畫轉場、骨架屏、樂觀更新。

---

## R-14：測試策略

**Decision**: 三層，對應憲章的必測要求：

| 層級 | 檔案 | 涵蓋 |
|------|------|------|
| 單元（不需 DB） | `tests/unit/test_admin_roles.py` | 名單核對：在名單內 → admin；不在名單內 → user；名單為空 → 全部為 user；名單含空白／換行的容錯；**已是 admin 但被移出名單 → 降回 user**（FR-007 的關鍵路徑） |
| 整合（真 PostgreSQL） | `tests/integration/test_admin_access_control.py` | **對全部 10 支管理端端點各發一次一般使用者請求，斷言皆為 403 且回應內容完全相同**；未登入請求皆為 401 |
| 整合（真 PostgreSQL） | `tests/integration/test_admin_stores.py` | CRUD 正常流程；座標成對驗證；座標範圍驗證；營養數值負數被拒；刪除店家後餐點數為 0（cascade）；對不存在的店家操作回 404 |

**Rationale**:

1. 憲章「開發流程與品質門檻」明列必測情境「一般使用者存取管理端 API 被拒絕」。第一輪已在單元層測了 `require_admin()` 本身，但那證明的是「函式邏輯正確」，不是「每一支端點都掛上了它」。**整合層逐端點驗證才是對 R-02 掛載正確性的真正檢查**，也是 FR-015「所有拒絕回應彼此一致」唯一可自動化的驗證方式。
2. cascade 刪除必須在真 PostgreSQL 上驗證——`ON DELETE CASCADE` 是資料庫層行為，SQLite 預設甚至不啟用外鍵約束。既有 conftest 已備妥 testcontainers 方案，直接沿用。
3. 名單核對邏輯純粹是字串集合運算，不需要 DB，放單元層可在無 Docker 環境下持續執行。

**測試資料建立方式**：整合測試以既有 `db_session` fixture 直接建立 `User(role=...)`，不經過 LINE Login（那需要外部服務）。登入流程本身的角色核對由單元測試涵蓋。
