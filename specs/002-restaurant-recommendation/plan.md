# Implementation Plan: 推薦餐廳（第二輪）

**Branch**: `feature/round2-restaurant` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-restaurant-recommendation/spec.md`；技術規劃補充依據 [reference/round2-plan-brief.md](../../reference/round2-plan-brief.md)；資料表共用契約 [reference/shared-schema-store-menu.md](../../reference/shared-schema-store-menu.md) ＋ **2026-08-04 第三輪交接說明**

> **契約檔案已於 2026-08-04 同步**（`menu_items` 補上 `created_at`／`updated_at`）。
> 契約檔案本身僅載明欄位名稱；交接說明另外議定了本輪讀取端必須遵守的語意
> （座標選填、名稱不唯一、實刪除＋CASCADE、營養值 0 為有效數值），兩者一併構成
> 本輪的資料層依據。本輪的 spec、research、data-model 與 contracts 均已依此更新。

## Summary

本輪在既有服務上新增一個**僅於 LIFF 入口提供**的推薦餐廳模組：使用者進入該模組時請求定位權限，後端依其座標計算與各店家的直線距離，回傳 5 公里內最近的 10 家；點選店家可瀏覽該店餐點的熱量與三大營養素。定位被拒或定位服務失敗時，各自以不同的說明退回「全部店家清單」，不阻斷模組。

技術取徑：**不新增任何技術選型**。距離以 Haversine 公式在 **Python 應用層**計算（不引入 PostGIS，理由見 R-01）；店家／餐點資料表欄位**完全依照共用契約**，本輪只建立 GET 端點，寫入端點屬第三輪；測試資料以可重複執行的 seed script 提供，不寫入 migration。

三項對後續影響最大的決策：

1. **第一輪沒有可重用的權限元件**（R-02）——相機是 `<input capture>` 交由作業系統處理，前端沒有任何 Permissions API 呼叫，因此偵測不到「被拒絕」。本輪的定位權限必須自建，「比照第一輪」只能在 UX 原則層級成立。這也正是本輪能滿足 FR-007（區分拒絕與失敗）的原因：geolocation 有錯誤碼，file input 沒有。
2. **共用契約的未定義處已由 2026-08-04 第三輪交接結案四項**（座標選填、名稱不唯一、實刪除＋CASCADE、`menu_items` 補時間戳），但**主鍵型別（OQ-1）與營養欄位 nullability（OQ-2b）仍未定案**。因交接同時議定「由先合併回 `main` 的一方建表」，先建表者等於為雙方定案，這兩項必須在任一方建表前取得共識。
3. **空狀態語意由 API 提供**（R-05）——回應恆帶 `total_store_count`，前端才能區分「附近沒有」與「根本沒有」，兩者的文案與操作不同。

## Technical Context

**Language/Version**: TypeScript 5.x / Node.js 20 LTS（前端）；Python 3.12（後端）——與第一輪相同

**Primary Dependencies**: 與第一輪完全相同，**本輪不新增任何套件**

- 前端 — Next.js 15（App Router）、React 19、`@line/liff`、Tailwind CSS、TanStack Query
- 後端 — FastAPI、Pydantic v2、SQLAlchemy 2.0、Alembic
- 距離計算使用 Python 標準庫 `math`，不需要 geopy 等第三方套件

**Storage**: PostgreSQL（Supabase）。本輪新增 `stores`、`menu_items` 兩張表，**不修改**第一輪任何資料表

**Testing**: pytest（後端單元／整合）、Vitest + React Testing Library（前端單元）、Playwright（端對端）——沿用第一輪既有設定

**Target Platform**: 後端 Vercel serverless（`root_path` 已於第一輪處理）；前端行動優先網頁，**本模組僅於 LINE App 內建瀏覽器（LIFF）呈現**

**Project Type**: Web application（在既有 `backend/` + `frontend/` 上增量開發）

**Performance Goals**:

- 店家清單與餐點清單 2 秒內完成呈現（SC-007）
- 距離計算：店家數 ≤ 1,000 筆時應用層全表計算耗時 < 10 ms，不構成瓶頸（R-01）

**Constraints**:

- 店家／餐點資料表欄位不得增減或改名（共用契約，brief 明訂）
- 本輪只提供 GET，不預先實作或預留寫入端點（brief 明訂）
- 不引入 PostGIS 或其他地理資料庫擴充（brief 明訂）
- 不得與第一輪通用食物營養對照表建立任何關聯（憲章原則 V）
- 後端不得因入口分岔（憲章原則 III 與架構約束）
- 不做地址→座標的地理編碼（brief 明訂，座標由第三輪後台人工輸入）

**Scale/Scope**: 店家數十筆量級；後端新增 3 支 GET 端點、2 張資料表；前端新增 2 個路由頁面與 1 個導覽分頁

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

依 [.specify/memory/constitution.md](../../.specify/memory/constitution.md) v1.0.0 逐條檢核。

| 原則 | 檢核項 | Phase 0 前 | Phase 1 後 | 落實位置 |
|---|---|---|---|---|
| **I. 統一 LINE 登入**（NON-NEGOTIABLE） | 不新增任何並行帳密體系 | ✅ | ✅ | 本輪無任何 auth 端點；沿用第一輪 `get_current_user()` |
| | 不為本模組分岔驗證路徑 | ✅ | ✅ | [contracts/openapi.yaml](./contracts/openapi.yaml) 三支端點共用 `bearerAuth`，無入口專用端點 |
| **II. 環境自我偵測** | 具備 LIFF 判斷能力，不假設 LIFF | ✅ | ✅ | 沿用 [environment.ts](../../frontend/src/lib/liff/environment.ts) 的 `isInLiff()`；非 LIFF 進入 `/restaurants` 走明確降級畫面而非崩潰（R-03、quickstart V9） |
| **III. 單一後端多客戶端** | 四端共用同一組端點、不因客戶端分岔 | ✅ | ✅ | R-03：LIFF-only 落實於**前端入口**，後端不檢查來源 |
| | 客戶端不保留離線業務資料 | ✅ | ✅ | 店家／餐點每次即時取自後端；座標僅存於 query cache（頁面生命週期內），非持久化（R-10、FR-012） |
| **IV. 角色與權限隔離**（NON-NEGOTIABLE） | 不以前端隱藏充當權限控制 | ✅ | ✅ | 本輪唯讀資料對所有登入者相同，**不涉及**管理端權限；寫入端點屬第三輪，屆時掛載既有的 `require_admin()` |
| **V. 營養資料表分離** | 兩套營養資料獨立、無外鍵 | ✅ | ✅ | [data-model.md](./data-model.md)：唯一外鍵是 `menu_items.store_id → stores.id`；migration 不觸碰第一輪任何表 |
| | 查詢路徑各自獨立 | ✅ | ✅ | `services/stores.py` 不 import 第一輪營養模組（測試斷言，R-11）；驗證情境 quickstart V11 |
| **VI. 技術棧約定** | Next.js + FastAPI + PostgreSQL | ✅ | ✅ | 本文件 Technical Context |
| | 不為單一功能引入平行框架／資料庫 | ✅ | ✅ | 明確否決 PostGIS（R-01）；距離計算僅用標準庫 `math` |
| **VII. 免責範圍**（NON-NEGOTIABLE） | 不提供醫療診斷；明示為估算值 | ✅ | ✅ | spec FR-037／FR-038；quickstart V13 |

**Gate 結論**：Phase 0 前後皆通過，**無違規項**，Complexity Tracking 無需填寫。

一項需要說明的判斷：憲章原則 III 要求「後端 API 契約對四端一致」，而 spec 要求本模組「僅於 LIFF 入口提供」。兩者不衝突——「僅 LIFF 提供」界定的是**哪個入口實作這個畫面**（功能範圍），不是**誰可以呼叫這個 API**（安全邊界）。若在後端依入口拒絕請求，才會構成違規。完整論證見 [research.md](./research.md) R-03，此判斷亦已記於 spec 的 Assumptions。

## Project Structure

### Documentation (this feature)

```text
specs/002-restaurant-recommendation/
├── plan.md                          # 本檔（/speckit-plan 輸出）
├── spec.md                          # 功能規格（/speckit-specify 輸出）
├── research.md                      # Phase 0：11 項技術決策 + 8 項 Open Questions
├── data-model.md                    # Phase 1：2 張資料表（受共用契約約束）、查詢管線
├── quickstart.md                    # Phase 1：環境設定與 13 組驗證情境
├── contracts/
│   └── openapi.yaml                 # 本輪新增的 3 支 GET 端點
├── checklists/
│   └── requirements.md              # 規格品質檢查（17/17 通過）
└── tasks.md                         # Phase 2（/speckit-tasks 產出，本指令不建立）
```

### Source Code (repository root)

只列出**本輪新增或修改**的檔案；未列出者不在本輪異動範圍。

```text
backend/
├── app/
│   ├── api/v1/
│   │   └── stores.py                # ★ 新增：3 支 GET 端點（僅 GET，FR-029）
│   ├── core/
│   │   └── config.py                # 修改：加 NEARBY_RADIUS_KM=5.0、NEARBY_LIMIT=10
│   ├── db/models/
│   │   └── store.py                 # ★ 新增：Store 與 MenuItem 兩個 model 同檔
│   ├── schemas/
│   │   └── store.py                 # 新增：StoreOut、StoreListResponse、MenuItemOut
│   ├── services/
│   │   ├── geo.py                   # ★ 新增：haversine_km() 純函式
│   │   └── stores.py                # ★ 新增：查詢管線（順序不可調換）
│   ├── scripts/
│   │   └── seed_stores.py           # ★ 新增：測試資料，可重複執行、可 --purge
│   ├── db/models/__init__.py        # 修改：匯出 Store、MenuItem（供 Alembic 掃描）
│   └── main.py                      # 修改：v1.include_router(stores.router)
├── alembic/versions/
│   └── 20260804_0002_store_menu.py  # ★ 新增：revision 0002，down_revision 0001
└── tests/
    ├── unit/test_geo.py             # 新增：Haversine 已知距離與邊界
    ├── unit/test_stores_query.py    # 新增：查詢管線順序、半徑邊界、截斷
    └── integration/test_stores_api.py  # 新增：三種空狀態、401/404、無寫入端點

frontend/
├── src/
│   ├── app/(app)/restaurants/
│   │   ├── page.tsx                 # ★ 新增：店家清單（含 4 種狀態分支）
│   │   └── [storeId]/page.tsx       # 新增：餐點瀏覽
│   ├── components/
│   │   ├── restaurants/
│   │   │   ├── StoreCard.tsx        # 新增
│   │   │   ├── MenuItemRow.tsx      # 新增：營養缺值顯示「無資料」
│   │   │   └── states.tsx           # ★ 新增：拒絕／失敗／附近查無／尚無資料 四種畫面
│   │   └── ui/
│   │       ├── PermissionNotice.tsx # ★ 新增：權限說明的共用呈現元件（R-02）
│   │       └── BottomNav.tsx        # 修改：新增「找餐廳」分頁，僅 LIFF 顯示
│   ├── lib/
│   │   ├── geo/location.ts          # ★ 新增：geolocation 包裝，錯誤碼 → 狀態
│   │   ├── format/distance.ts       # 新增：公尺／公里格式化
│   │   └── api/
│   │       ├── endpoints.ts         # 修改：加 storeApi
│   │       └── types.ts             # 修改：加 Store、MenuItem 型別
│   └── hooks/
│       └── useCurrentLocation.ts    # ★ 新增：座標的 TanStack Query 封裝（R-10）
└── tests/
    ├── unit/                        # location.ts 錯誤碼映射、距離格式化、缺值顯示
    └── e2e/                         # V1、V8、V9 路徑
```

**Structure Decision**: 沿用第一輪的 `backend/` + `frontend/` 雙目錄結構，本輪為純增量——不移動、不重構任何既有檔案，對第一輪檔案的修改僅限於 5 處**追加式**改動（config 兩個常數、models 匯出、router 註冊、endpoints/types 新增、BottomNav 加一個分頁）。這使本輪與第三輪的合併衝突面收斂到共用契約的兩張表本身。

`Store` 與 `MenuItem` 兩個 model **刻意放在同一個檔案** `db/models/store.py`，而非依第一輪「一個 model 一個檔」的慣例拆開，理由有二：(a) 兩者是共用契約的單一單元，必須同進同出，放一起可讓與第三輪的合併衝突集中於一個檔案；(b) 若另建 `menu_item.py`，與既有的 `meal_item.py`（第一輪的飲食紀錄品項）只差兩個字母，是明確的誤讀風險——而這兩者恰好是憲章原則 V 要求嚴格隔離的兩套資料，混淆的代價很高。

上表以 ★ 標記者為本輪**架構關鍵點**：

| 檔案 | 承載的約束 |
|---|---|
| `services/geo.py` | R-01：距離公式集中於純函式，可無資料庫單元測試（SC-002 的驗證基礎） |
| `services/stores.py` | R-04：查詢管線順序固定；FR-018／FR-020 的正確性全繫於此 |
| `api/v1/stores.py` | FR-029：**只有 GET**，不預留寫入端點 |
| `db/models/store.py` | 共用契約：欄位不得增減改名；合併衝突的集中點 |
| `scripts/seed_stores.py` | FR-033〜035：不寫入 migration、可重複執行、`[測試]` 前綴可識別 |
| `lib/geo/location.ts` | FR-007：`GeolocationPositionError.code` → 拒絕／失敗兩條路徑的唯一分歧點 |
| `hooks/useCurrentLocation.ts` | R-10：讓「返回不重取、重載才重取」同時成立（FR-026 vs US1-7） |
| `components/restaurants/states.tsx` | SC-004／SC-005：四種狀態畫面必須彼此可區分 |
| `components/ui/BottomNav.tsx` | FR-002：非 LIFF 不得呈現入口，且判定完成前不得閃現 |

## 關鍵架構決策摘要

完整論證見 [research.md](./research.md)，此處摘錄影響最大的四項。

### 1. 距離計算放應用層，不放 SQL（R-01）— brief 要求明確說明取捨

**採用應用層 Haversine**。決定性理由是**可測試性**：`haversine_km()` 是純函式，能在沒有資料庫的情況下驗證已知距離、同點為零、經度換日線與極值座標，而距離排序的正確性正是本輪最核心的可測邏輯（SC-002）。SQL 內嵌 Haversine 需以 `sa.func.acos(sa.func.sin(...))` 層層包裝，既難讀又必須起資料庫才能驗證。

應用層的代價是每次查詢取回全表，但在 brief 明示的「店家數量不大」前提下不成立為問題（數十筆的計算耗時遠低於一次網路往返）。**成長觸發點已寫入 R-01**：約 1,000 筆前無需處理，超過後先加 SQL bounding box 粗篩，仍不足才評估 PostGIS——先寫下來，避免日後憑感覺改架構。

### 2. 第一輪的相機權限模式在程式碼中不存在（R-02）

brief 要求「比照第一輪相機權限的既有實作模式」，實際查核結果是**沒有可沿用的元件或流程**：第一輪用 `<input type="file" capture="environment">`，權限由作業系統的檔案選擇器處理，前端沒有呼叫任何 Permissions API，因此**偵測不到權限是否被拒**——它的「被拒處理」是一段恆常顯示的靜態提示加上「從相簿選取」按鈕，並非依權限狀態分支。

因此本輪沿用的是其 **UX 原則**（不預先請求、被拒不阻斷、明示如何恢復），而**實作全新**。共用可行性的評估結論：取得機制無共同抽象、不可共用；**呈現層可以**，故本輪建立 `PermissionNotice` 元件。第一輪改用此元件列為**可選後續改善**，不列入本輪範圍——已驗收的流程不為形式一致而承擔回歸風險。

### 3. 空狀態的語意差異必須由 API 給（R-05）

回應恆帶 `total_store_count`（不受半徑與筆數限制影響的店家總數）。若前端只看 `stores: []`，「附近沒有」與「根本沒有」長得完全一樣——但前者要提供「改看全部店家」，後者提供這個按鈕只會導向另一個空清單。這是最容易在實作契約時漏掉的欄位。

### 4. 座標交給 TanStack Query 承載（R-10）

規格有兩條看似衝突的要求：從餐點頁返回時**不得**重新請求權限（FR-026），重新載入頁面時**必須**重新取得座標（US1-7）。以 query cache 保存座標可讓兩者自然成立：client-side 導覽時 cache 命中，整頁重載時 cache 隨頁面銷毀。改用 `sessionStorage` 會違反後者，改用元件 state 會違反前者。

## Open Questions

完整清單與建議值見 [research.md](./research.md)（含已結案項目的對照表）。跨分支的協調事項依 brief 指示提出，不自行決定後逕行實作。

**2026-08-04 第三輪執行清單給出最終欄位定義後，跨分支的 Open Question 全數結案**（對照表見 [research.md](./research.md)）：主鍵 UUID、營養欄位 nullable、經緯度 nullable 且以 DB CHECK 保證成對、`name` VARCHAR(255) 不唯一、`address` VARCHAR(500) NOT NULL、`ON DELETE CASCADE`、建表由第三輪負責。

僅餘兩項與第三輪無關的本輪自身待辦：

| ID | 問題 | 現行值 | 需在何時決定 |
|---|---|---|---|
| OQ-7 | 5 公里半徑是否符合實際使用情境 | 5.0 km（已於 specify 階段決定） | 實地測試後 |
| OQ-8 | 地址→座標的自動地理編碼 | 不做（brief 明訂） | 第三輪或之後 |

## ⚠️ 與第三輪分支的合併風險（brief 要求記錄）

本輪（`feature/round2-restaurant`）與第三輪管理員後台（`feature/round3-admin`）在不同分支平行開發，**共用同一張資料表但操作方向相反**——本輪讀、第三輪寫。

**2026-08-04 交接已議定建表歸屬**：兩張表在 `main` 與兩個分支上皆尚不存在，**由先合併回 `main` 的一方建立，另一方沿用**，誰先建立需於合併前互相知會。這消除了原先「雙方各自建表」的預設路徑，但風險並未歸零——若在知會前雙方都已產生 migration，下表第 1 項仍會發生。

依 2026-08-04 第三輪執行清單，兩邊已議定分工並各自消除了衝突源。以下為**現況**：

| # | 原風險 | 狀態 | 處置 |
|---|---|---|---|
| 1 | **Alembic 雙 head**（兩支 `0002` 同以 `0001` 為 parent） | ✅ **已消除** | 本輪的 `20260804_0002_store_menu.py` **已刪除**。DDL 由第三輪的 `20260804_0002_stores_menu_items.py` 提供——由寫入方持有 schema 是正確歸屬 |
| 2 | 主鍵型別不一致 | ✅ **已消除** | 雙方皆為 UUID |
| 3 | 營養欄位 nullability 衝突 | ✅ **已消除** | 雙方皆為 nullable；第三輪另有測試斷言 NULL 不會被寫成 0 |
| 4 | **`models/store.py` 同檔名不同內容** | 🟡 **降為易解** | 本輪已改為與第三輪相同的組織方式（`store.py` = `Store`、`menu_item.py` = `MenuItem`），欄位逐項比照其最終定義。合併時**直接採用第三輪版本**，本輪查詢程式碼零改動 |
| 5 | `services/stores.py` 同檔名衝突 | ✅ **已消除** | 第三輪主動改名為 `services/admin_stores.py`，本輪不需異動 |
| 6 | 測試資料混入正式環境 | 🟢 **已控制** | 本輪刻意不放進 migration（需手動執行），並提供 `--purge`。第三輪後台上線後，`seed_stores.py` 降為「快速鋪測試資料」的工具而非唯一資料來源 |
| 7 | **語意約定未進入契約檔案** | 🟡 **仍待處理** | 「座標選填且成對」「名稱不唯一」「實刪除＋CASCADE」「0 為有效數值」等行為約定目前散落於兩份交接說明中，契約檔案只有欄位清單。建議合併時補入，本輪已完整記錄於 [data-model.md](./data-model.md) 可作為來源 |

**仍需人工處理的同檔追加（內容不衝突，保留雙方即可）**：

| 檔案 | 本輪加的 | 第三輪加的 |
|---|---|---|
| `app/db/models/__init__.py` | `Store`、`MenuItem` 匯出 | 同上（內容應相同，留一份） |
| `app/core/config.py` | `nearby_radius_km`、`nearby_limit` | `ADMIN_LINE_USER_IDS`（不同區塊） |
| `app/main.py` | `v1.include_router(stores.router)` | `admin_*` 三個 router（相鄰行，皆保留；⚠️ catch-all 404 那條必須維持在最後） |
| `frontend/src/lib/api/types.ts`、`endpoints.ts` | `Store`／`MenuItem` 型別與 `storeApi` | 同名型別（應一致，留一份） |

**本輪為何仍保留 model 檔案而非直接刪除**：直接刪除會使本分支在合併前無法執行任何測試、seed 或本機驗證（136 支後端測試全數失敗）。故保留為**可執行的鏡像**——同檔名、同組織方式、欄位逐項比照對方定義，合併時覆蓋即可。本輪依賴的是 `from app.db.models import Store, MenuItem` 這個第三輪已保證穩定的匯入介面，與檔案怎麼切無關。

## 本輪不處理

- 店家／餐點的新增、編輯、刪除介面與寫入端點——第三輪管理員後台
- 一般網頁、iOS、Android 三個入口的推薦餐廳畫面
- 地址→座標的自動地理編碼（座標由第三輪後台人工輸入）
- 店家搜尋、篩選、營業時間、照片、評分、分類標籤——共用契約未定義這些欄位
- 「將店家餐點一鍵記入飲食紀錄」——餐點瀏覽為唯讀資訊呈現，不與第一輪記帳流程串接
- 合作店家點餐流程與訂單系統 API
- 第一輪相機權限改用 `PermissionNotice` 元件——可選後續改善，見 R-02

## Complexity Tracking

Constitution Check 於 Phase 0 前與 Phase 1 後**皆無違規項**，本節無需填寫。

設計過程中被明確否決的複雜度：PostGIS 與空間索引（R-01）、SQL 內嵌距離公式（R-01）、Permissions API 預查詢（R-02）、後端入口來源檢查（R-03）、拆成 `/stores` 與 `/stores/nearby` 兩個端點（R-06）、前端自行計算距離與排序（R-06）、以 `sessionStorage` 保存座標（R-10）。每一項的否決理由均為「本輪規模下成本超過收益，或牴觸憲章與 brief 的明確約束」。
