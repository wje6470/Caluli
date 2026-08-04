# Implementation Plan: 管理員角色與店家／餐點後台（第三輪）

**Branch**: `feature/round3-admin` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-admin-backoffice/spec.md`；技術規劃補充依據為 [reference/round3-plan-brief.md](../../reference/round3-plan-brief.md)

## Summary

啟用第一輪已預留的角色欄位與權限檢查層，新增店家／餐點兩張資料表與其後台維護介面。

技術路線的三個要點：

1. **權限層零新建**——第一輪已實作 `require_admin()`（[deps.py:53](../../backend/app/core/deps.py#L53)）且刻意未掛載於任何端點。本輪只需在管理端 router 上以 `dependencies=[Depends(require_admin)]` 統一掛載，不重寫授權邏輯，各端點內也不再手寫角色判斷（憲章「架構約束」）。
2. **管理員指派走部署設定 + 登入時核對**——名單存於環境變數，在兩個登入入口唯一的匯流點 `upsert_user()`（[line_auth.py:107](../../backend/app/services/line_auth.py#L107)）核對並同步 `users.role`。全系統不存在任何可寫入 role 的 API。
3. **資料表完全依共用契約建立**——`stores` / `menu_items` 欄位逐一對應 [shared-schema-store-menu.md](../../reference/shared-schema-store-menu.md)，migration 不自行增減欄位；座標 nullable 並以 CHECK 約束強制成對；`menu_items.store_id` 設 `ON DELETE CASCADE`。

後台介面以原生 table + form 實作，不引入任何元件庫，重點放在寫入正確性而非視覺。

## Technical Context

**Language/Version**: Python 3.12（後端）、TypeScript / Node.js（前端，Next.js App Router）

**Primary Dependencies**: FastAPI ≥0.115、SQLAlchemy ≥2.0.36、Alembic ≥1.14、pydantic ≥2.9 / pydantic-settings ≥2.6、psycopg ≥3.2；前端 Next.js + TanStack Query + Tailwind。**本輪不新增任何依賴套件**（憲章原則 VI）。

**Storage**: PostgreSQL（本機 Docker、正式環境 Supabase Session pooler）。本輪新增 2 張資料表，不修改既有 6 張表的結構。

**Testing**: pytest + testcontainers（整合測試跑真 PostgreSQL，見 [conftest.py](../../backend/tests/conftest.py)）；不依賴 DB 的權限層測試放 `tests/unit/`。

**Target Platform**: 後端為 Linux 容器 / Vercel serverless；後台介面為桌機瀏覽器（非 LIFF、非行動裝置最佳化）。

**Project Type**: Web application（既有 `backend/` + `frontend/` 雙目錄）

**Performance Goals**: 無特殊要求。後台使用者為個位數內部人員，店家數十至數百筆、單店餐點數十筆以內，所有查詢皆為單表或單一 JOIN，不需要分頁、索引調校或快取。

**Constraints**:

- `stores` / `menu_items` 欄位結構受共用契約約束，**不得自行增減或更名**（第二輪分支平行讀取同一張表）。
- 不得修改第一輪既有的使用者資料表結構語意、LINE Login 驗證邏輯或既有 API 行為（FR-043）。
- 管理端 API 與一般使用者 API 必須分開掛載，權限判斷一律在後端（憲章原則 IV，NON-NEGOTIABLE）。

**Scale/Scope**: 後端新增 2 個 model、1 個 migration、2 個 service、3 個 router 檔、1 個 schema 檔；前端新增 1 個路由群組（3 個頁面）+ 3 個元件。管理員人數個位數。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 初次評估（Phase 0 前）

| # | 原則 | 判定 | 依據 |
|---|------|------|------|
| I | 統一 LINE 登入（NON-NEGOTIABLE） | ✅ PASS | 管理員與一般使用者走完全相同的 `login_with_id_token()`，不新增帳密登入路徑。角色核對發生在身分驗證**之後**的 `upsert_user()`，不分岔驗證邏輯（R-03）。 |
| II | 執行環境自我偵測，不假設 LIFF | ✅ PASS | 後台為一般網頁介面，不呼叫任何 LIFF SDK 能力，亦不預設執行於 LIFF context；後台不掛在 LIFF 入口下。 |
| III | 單一後端，多客戶端即時呼叫 | ✅ PASS | 管理端 API 掛在同一個 FastAPI 應用的同一個 `/api/v1` router 下（R-01），非另起服務。後台不保留任何本機業務資料，全部即時取自後端。 |
| IV | 角色與權限隔離（NON-NEGOTIABLE） | ✅ PASS | 本輪核心。權限檢查層為既有的獨立可測元件 `require_admin()`，於 router 層統一掛載（R-02）；管理端與一般使用者 API 分開掛載；判斷全在後端，前端隱藏僅為輔助。 |
| V | 營養資料表分離 | ✅ PASS | `stores` / `menu_items` 與 `food_nutrition_references` 之間**無任何外鍵、無共用主鍵語意、無型別欄位混存**。migration 沿用第一輪慣例附稽核註記。 |
| VI | 技術棧約定 | ✅ PASS | 未引入任何新框架、資料庫或執行環境；後台刻意不引入 UI 元件庫（R-13）。 |
| VII | 免責範圍（NON-NEGOTIABLE） | ✅ PASS | 後台為內部資料維護介面，不對終端使用者呈現營養估算結果，不產生任何醫療性判讀。店家餐點營養值為店家登錄的既定數值，其對使用者的呈現方式屬第二輪範圍。 |

### 再次評估（Phase 1 設計後）

設計產出（data-model.md、contracts/admin-api.yaml、quickstart.md）逐項複查後，**判定不變，仍全數 PASS**。三項設計決定強化了原本的判定：

- 原則 IV：契約層讓全部 10 支管理端端點共用同一個 `Forbidden` 回應定義，使「拒絕回應彼此一致」在 OpenAPI 層即可驗證，而非僅靠實作自律。
- 原則 V：data-model.md 附完整稽核，確認兩張新表的出向／入向外鍵皆不觸及 `food_nutrition_references`。
- 原則 I：`GET /admin/me` 不回傳任何 LINE 憑證資訊，僅回傳角色判定結果，未擴大身分資料的暴露面。

**開發流程與品質門檻對應**：

- 憲章必測情境「一般使用者存取管理端 API 被拒絕」：第一輪已有 [test_deps.py](../../backend/tests/unit/test_deps.py) 直接測試依賴本身；本輪**再補整合層測試**，以真實 HTTP 請求驗證每一支管理端端點對一般使用者皆回 403（quickstart 驗證 3）。
- 憲章必測情境「非 LIFF 環境可完成登入流程」：本輪未改動登入流程，第一輪既有測試持續適用；本輪僅新增「登入時角色核對」的單元測試。
- 未引入超出既有技術棧的元件，無需書面說明替代方案評估。

**結論：無違反項，Complexity Tracking 留空。**

## Project Structure

### Documentation (this feature)

```text
specs/003-admin-backoffice/
├── plan.md              # 本檔
├── research.md          # Phase 0：14 項技術決策 + 3 項 open question
├── data-model.md        # Phase 1：2 張新表、欄位對應契約、約束與 cascade
├── quickstart.md        # Phase 1：環境設定、指派管理員、6 項驗證情境
├── contracts/
│   └── admin-api.yaml   # Phase 1：管理端 OpenAPI 契約
├── checklists/
│   └── requirements.md  # /speckit-specify 產出
└── tasks.md             # Phase 2（/speckit-tasks 產出，非本命令範圍）
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 20260804_0002_stores_menu_items.py   # 新增：2 張表 + 憲章原則 V 稽核註記
├── app/
│   ├── api/v1/
│   │   ├── admin_stores.py                  # 新增：店家 CRUD（router 層掛 require_admin）
│   │   ├── admin_menu_items.py              # 新增：餐點 CRUD（同上）
│   │   └── admin_session.py                 # 新增：GET /admin/me，供前端守衛探測
│   ├── core/
│   │   ├── config.py                        # 修改：新增 admin_line_user_ids 設定
│   │   └── deps.py                          # 不修改：require_admin 已存在且可直接使用
│   ├── db/models/
│   │   ├── store.py                         # 新增：Store
│   │   ├── menu_item.py                     # 新增：MenuItem（⚠️ 與既有 MealItem 名稱相近）
│   │   └── __init__.py                      # 修改：匯出新 model 供 Alembic 掃描
│   ├── schemas/
│   │   └── admin.py                         # 新增：Store / MenuItem 的 In/Out schema
│   ├── services/
│   │   ├── admin_roles.py                   # 新增：名單核對與角色同步
│   │   ├── stores.py                        # 新增：店家／餐點 CRUD 業務邏輯
│   │   └── line_auth.py                     # 修改：upsert_user() 內呼叫角色核對
│   └── main.py                              # 修改：掛載 3 個 admin router
└── tests/
    ├── unit/
    │   ├── test_deps.py                     # 既有：權限層本身（不修改）
    │   └── test_admin_roles.py              # 新增：名單核對的升／降級與邊界
    └── integration/
        ├── test_admin_access_control.py     # 新增：每支管理端端點對一般使用者皆 403
        └── test_admin_stores.py             # 新增：CRUD、座標驗證、cascade 刪除

frontend/
└── src/
    ├── app/admin/                           # 新增：刻意**不放在 (app) 群組內**（R-10）
    │   ├── layout.tsx                       # 管理員守衛 + 極簡外框（無 BottomNav）
    │   ├── page.tsx                         # 店家清單 + 新增／編輯／刪除
    │   └── stores/[storeId]/page.tsx        # 該店家的餐點清單 + CRUD
    ├── components/admin/
    │   ├── StoreForm.tsx                    # 表單（含座標成對驗證與提示文字）
    │   ├── MenuItemForm.tsx
    │   └── ConfirmDialog.tsx                # 刪除二次確認（顯示連帶刪除的餐點數）
    └── lib/api/
        ├── endpoints.ts                     # 修改：新增 adminApi
        └── types.ts                         # 修改：新增 Store / MenuItem 型別
```

**Structure Decision**: 沿用第一輪已確立的 `backend/` + `frontend/` 雙目錄結構，不新增頂層目錄。管理端後端程式碼以 `admin_` 前綴的檔名與一般使用者端點並列於 `app/api/v1/`——同一個 router 樹、同一份錯誤信封，符合憲章原則 III「單一後端」；**隔離由 router 層的依賴掛載達成，而非由目錄或服務切割達成**（理由見 R-01、R-02）。

前端後台刻意放在 `src/app/admin/` 而**不放進既有的 `(app)` 路由群組**：`(app)/layout.tsx` 會強制未完成健康檔案者導向 `/onboarding`，而管理員可能從未填寫個人健康資料，放進去會讓管理員被自己的產品擋在後台之外（R-10）。

## Complexity Tracking

> 無憲章違反項，本節不適用。

## Phase 0 — Research 摘要

完整內容見 [research.md](./research.md)。14 項決策中，對實作影響最大的五項：

| 編號 | 決策 | 一句話理由 |
|------|------|-----------|
| R-01 | 管理端前綴用 `/api/v1/admin/*`，非 brief 舉例的 `/api/admin/*` | 前端 `NEXT_PUBLIC_API_BASE_URL` 已含 `/api/v1`，另立前綴需要第二個 base URL 環境變數；且前綴不是安全邊界，依賴掛載才是 |
| R-02 | 在 `APIRouter(dependencies=[Depends(require_admin)])` 掛載，非逐端點掛 | 新增端點時**不可能忘記加**權限檢查；憲章明令不得在各端點重複手寫判斷 |
| R-03 | 名單存環境變數，於 `upsert_user()` 核對並雙向同步 role | 兩個登入入口唯一的匯流點，改一處即涵蓋 LIFF 與網頁；名單為單一真實來源，可宣告式撤銷 |
| R-05 | 一般使用者一律回 403，接受「403/404 差異可推知路徑存在」的殘留 | 與 spec 假設一致（後台網址不視為機密，安全性由權限層保證）；回應內容本身不透露任何功能語意 |
| R-07 | `menu_items.store_id` 設 `ON DELETE CASCADE` | spec FR-037 已定案連帶刪除；DB 層 cascade 讓「殘留無主餐點」在結構上不可能發生，而非依賴應用層記得刪 |

### Open Questions（不阻擋實作，需人工決策或跨分支協調）

- **OQ-1（brief 明確要求評估）**：共用契約目前**足以**支撐本輪所有寫入需求，**不需要新增任何欄位**。唯一評估過的候選是「是否上架顯示」（`is_active`），已於 spec 階段決定不加——延後加入無資料遷移風險（新欄位預設上架、既有資料全視為上架），而提前加入會讓讀取端每個查詢多一個可能漏加的過濾條件。此處僅記錄：若日後出現「店家暫時休業」需求，須以契約修訂處理並知會第二輪，**不得**由本輪逕行加欄位。
- **OQ-2（brief 明確要求記錄）**：本輪先建立 migration 時與第二輪分支的版次衝突風險，詳見下方「與第二輪分支的合併風險」。**本輪不處理，僅記錄。**
- **OQ-3**：管理員名單移除後需下次登入才生效（最長 7 天，等同 `jwt_expires_seconds` 效期）。若營運上需要即時撤銷，須走「直接改資料庫 role + 同步移除名單」的雙步驟（見 quickstart 的撤銷流程）。本輪不實作即時撤銷機制，因管理員為個位數內部人員。

## Phase 1 — Design 摘要

- **[data-model.md](./data-model.md)**：`stores`（7 欄）與 `menu_items`（9 欄）逐欄對應共用契約；座標 nullable + `CHECK` 強制成對 + 範圍約束；`MenuItem` 與既有 `MealItem` 的命名區辨說明；憲章原則 V 稽核結論。
- **[contracts/admin-api.yaml](./contracts/admin-api.yaml)**：10 支管理端端點的 OpenAPI 契約，全部共用同一個 `Forbidden` 回應定義（使 FR-015 的「回應彼此一致」在契約層即成立）。
- **[quickstart.md](./quickstart.md)**：如何指派第一位管理員、如何撤銷、6 項端到端驗證情境。

### 與第二輪分支的合併風險（OQ-2，需人工確認，本輪不處理）

`feature/round3-admin` 與 `feature/round2-restaurant` 共用 `stores` / `menu_items`，但兩個分支都可能各自建立 migration 與 model。合併前必須人工確認以下三點：

1. **migration 版次衝突**：兩邊都以 `down_revision = "0001"` 為基礎時，合併後 Alembic 會出現兩個 head，`alembic upgrade head` 會直接失敗。需由後合併的一方把自己的 `down_revision` 改指向先合併者的 revision，形成單一線性鏈。
2. **重複建表**：若兩邊都寫了 `create_table("stores", ...)`，合併後第二支 migration 在執行時會報 `relation already exists`。應由先合併的一方保留建表 migration，後合併者刪除自己的建表 migration。欄位既然同源於同一份契約，內容理應一致；**若比對後不一致，代表有一方偏離了契約，須先對齊再合併**。
3. **model 檔重複**：`app/db/models/store.py` 與 `menu_item.py` 兩邊都會建立，合併時為文字衝突。應以共用契約為準逐欄比對後保留一份。

**建議的協調方式（需雙方人工確認，本輪不代為決定）**：由本輪（寫入端）先合併並負責建表，第二輪僅保留讀取用的查詢程式碼，刪除自己的建表 migration 與 model 定義。理由是寫入端必須定義完整的約束（NOT NULL、CHECK、ON DELETE），讀取端不需要也不應該重複定義這些；反過來若由讀取端建表，很可能漏掉只有寫入端才會用到的約束。
