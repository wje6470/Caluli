---
description: "Task list for 管理員角色與店家／餐點後台（第三輪）"
---

# Tasks: 管理員角色與店家／餐點後台（第三輪）

**Input**: Design documents from `/specs/003-admin-backoffice/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/admin-api.yaml](./contracts/admin-api.yaml)、[quickstart.md](./quickstart.md)

**Tests**: **包含測試任務**。憲章「開發流程與品質門檻」明定：涉及登入、權限或營養資料表的變更必須具備對應測試，且必測情境包含「一般使用者存取管理端 API 被拒絕」。測試策略見 [research.md R-14](./research.md#r-14測試策略)。

**Organization**: 依 user story 分組，每個 story 可獨立實作與驗收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行執行（不同檔案、無未完成的前置依賴）
- **[Story]**: 對應 spec.md 的 user story（US1～US4）
- 每個任務都標明確切檔案路徑

## Path Conventions

Web app 結構（沿用第一輪）：後端 `backend/app/`、`backend/tests/`；前端 `frontend/src/`。

---

## Phase 1: Setup — 建表前的現況確認（阻塞 Phase 2）

**Purpose**: tasks brief 明確要求：不得直接假設需要新建表，先確認資料庫現況。

- [x] T001 檢查 `stores` / `menu_items` 的資料表與 migration 現況，確認本輪是否需要建表。執行 `ls backend/alembic/versions/`、`git ls-tree -r --name-only origin/main -- backend/alembic/versions`、`git ls-tree -r --name-only origin/feature/round2-restaurant -- backend/alembic/versions`，並在 `backend/app/db/models/` 下確認無 `store.py` / `menu_item.py`。將結論記錄於本檔末的「執行紀錄」。

  > **2026-08-04 已先行查證的結果**：`main`、`feature/round2-restaurant`、`feature/round3-admin` 三個分支的 `backend/alembic/versions/` 皆**只有** `20260803_0001_initial_schema.py`，且三者的 `backend/app/db/models/` 皆無店家／餐點 model。第二輪目前只完成 specify + plan，**尚未 implement**。
  > **結論：本輪需要建表**（T008）。
  > 惟實作開跑時第二輪可能已合併，故此任務仍須實際重跑一次確認；若屆時表已存在，**跳過 T005～T009 的建表部分**，改為核對既有結構是否符合 [data-model.md](./data-model.md)，不足處以 `alter` migration 補齊，**不得重複建表**。

- [x] T002 與第二輪開發者確認三項「建表前必須定案」的欄位決議，結論同步回 [reference/shared-schema-store-menu.md](../../reference/shared-schema-store-menu.md) 後才可執行 T008。**2026-08-04 已全數定案：**

  | 項目 | 定案結果 | 備註 |
  |------|---------|------|
  | 主鍵型別 | **UUID** + `gen_random_uuid()` | 雙方原提案即一致（第二輪 OQ-1） |
  | 四個營養欄位可否為 NULL | **nullable**（可為空值） | 第二輪 OQ-2b，**採納其主張**——本輪原為 NOT NULL，已改 |
  | `name` 欄位型別 | **`VARCHAR(255)`** | 與第一輪全專案的 `String(255)` 慣例一致。第二輪原提 `TEXT`；兩者對讀取端行為完全相同（PostgreSQL 中效能無差異，僅多一個長度上限），**不阻塞任何一方**，故從既有慣例 |

  > **營養欄位改為 nullable 的理由**：若設為 `NOT NULL`，「店家未提供該項數值」與「該項確實為 0」的區別在寫入當下即永久喪失，且會迫使管理員填入不實的 0。與本輪補時間戳所用的「不可逆性」論據同一類。
  >
  > **已連帶更新**：spec FR-032／FR-033 與 US3 驗收情境 5a／5b、[data-model.md](./data-model.md) 的欄位表與 CHECK 說明、[contracts/admin-api.yaml](./contracts/admin-api.yaml) 的 `MenuItemInput.required`（只剩 `name`）與三個 MenuItem schema 的 `nullable`、[共用契約檔](../../reference/shared-schema-store-menu.md) 的欄位語意補充第 2、3 點與變更紀錄。

**Checkpoint**: 現況已確認、三項決議已定案 → 可以建表

---

## Phase 2: Foundational（阻塞所有 user story）

**Purpose**: 資料表、model 與設定。tasks brief 要求 migration 排在最前面。

**⚠️ CRITICAL**: T008 必須在 T002 定案後才能執行。

- [x] T003 [P] 在 `backend/app/core/config.py` 的 `Settings` 新增 `admin_line_user_ids: str = ""`（逗號分隔字串，非 JSON 陣列）與 `admin_line_user_id_set` property，property 需 `strip()` 每個元素並過濾空字串後回傳 `frozenset[str]`。理由見 [research.md R-04](./research.md#r-04管理員名單的環境變數格式)。
- [x] T004 [P] 在 `backend/.env.example` 補上 `ADMIN_LINE_USER_IDS=`，附註格式為逗號分隔、留空代表無人是管理員、正式環境須以加密環境變數設定且不得提交進版控。
- [x] T005 [P] 建立 `backend/app/db/models/store.py`：`Store(Base, TimestampMixin)`，`__tablename__ = "stores"`，欄位 `id`／`name`／`address`／`latitude`／`longitude` 依 [data-model.md](./data-model.md) 的型別與可空性；加上三條 CHECK：`ck_stores_coords_paired`（`(latitude IS NULL) = (longitude IS NULL)`）、`ck_stores_latitude_range`、`ck_stores_longitude_range`。**不加 UNIQUE 於 name**（FR-027）。
- [x] T006 [P] 建立 `backend/app/db/models/menu_item.py`：`MenuItem(Base, TimestampMixin)`，`__tablename__ = "menu_items"`，`store_id` 為 `ForeignKey("stores.id", ondelete="CASCADE")` 且 `nullable=False`；`calories`／`protein_g`／`carbs_g`／`fat_g` 四者型別為 `Mapped[Decimal | None]`（**nullable，T002 定案**），四者皆加 `CHECK >= 0`（PostgreSQL 的 CHECK 對 NULL 求值為 UNKNOWN 而不拒絕，故不需額外寫 `IS NULL OR`）。在檔案 docstring 明確標註兩件事：（a）本類別與既有 `MealItem` 的語意差異與「兩者無任何關聯」；（b）**空值＝店家未提供、0＝確實為零，寫入時不得以 0 代替空值**。
- [x] T007 在 `backend/app/db/models/__init__.py` 匯入並加入 `__all__`：`Store`、`MenuItem`（供 Alembic autogenerate 掃描）。依賴 T005、T006。
- [x] T008 建立 `backend/alembic/versions/20260804_0002_stores_menu_items.py`：`revision = "0002"`、`down_revision = "0001"`；`upgrade()` 僅含 `create_table("stores")`、`create_table("menu_items")` 與 `create_index("ix_menu_items_store", "menu_items", ["store_id"])`，**不得含任何 `alter_table`**（FR-043）；`menu_items.store_id` 的外鍵須明確標註 `ondelete="CASCADE"`；`downgrade()` 反向 drop。依 [research.md R-12](./research.md#r-12migration-的版次與命名) 在 docstring 內寫入憲章原則 V 稽核紀錄（內容見 [data-model.md](./data-model.md) 的「憲章原則 V 稽核」一節）。依賴 T002、T007。
- [x] T009 執行 `cd backend && alembic upgrade head`，並以 `\d stores`、`\d menu_items` 驗證：`stores` 有 3 條 CHECK、`menu_items` 的 `store_id` 標註 `ON DELETE CASCADE`、`ix_menu_items_store` 索引存在。依賴 T008。

**Checkpoint**: 資料表就緒、設定就緒 → user story 可開始。US1 不依賴 T005～T009，急於取得 MVP 時可與其並行。

---

## Phase 3: User Story 1 — 管理員身分指派與後台存取控制 (Priority: P1) 🎯 MVP

**Goal**: 被指派的 LINE 帳號登入後成為管理員並可進入後台；一般使用者看不到任何入口，且以有效登入狀態呼叫任一管理端 API 一律被拒。

**Independent Test**: 準備一個在名單內、一個不在名單內的 LINE 帳號，各自登入後驗證 quickstart 的驗證 1～3。**此驗證不需要任何店家或餐點資料即可完成**。

### Tests for User Story 1 ⚠️

> 先寫測試並確認其失敗，再進行實作。

- [x] T010 [P] [US1] 建立 `backend/tests/unit/test_admin_roles.py`：涵蓋名單核對的 5 種情境——在名單內→`admin`；不在名單內→`user`；名單為空→全部為 `user`（且不報錯）；名單含空白與換行的容錯；**已是 `admin` 但被移出名單→降回 `user`**（FR-007 的關鍵路徑，只升不降的實作會在此失敗）。
- [x] T011 [P] [US1] 建立 `backend/tests/integration/test_admin_access_control.py`：**這是憲章原則 IV 明列的必測情境，獨立成檔以便單獨執行與驗收**。對 [contracts/admin-api.yaml](./contracts/admin-api.yaml) 定義的全部 10 支管理端端點各發一次請求，斷言：（a）持一般使用者有效 token 時全部回 **403**；（b）10 支端點的回應 body **逐字完全相同**（同 code、同 message、同 retryable），確保無法藉差異推測何者存在（FR-015）；（c）不帶 token 時全部回 **401** 而非 403（FR-016）；（d）寫入類請求（POST／PATCH／DELETE）執行後資料庫**無任何變更**（FR-014）。

### Implementation for User Story 1

- [x] T012 [US1] 建立 `backend/app/services/admin_roles.py`：實作 `resolve_role(line_user_id: str) -> str`，依 `get_settings().admin_line_user_id_set` 回傳 `ROLE_ADMIN` 或 `ROLE_USER`。此函式為**純函式、不碰資料庫**，使 T010 可在無 Docker 環境執行。依賴 T003。
- [x] T013 [US1] （另補 `backend/tests/integration/test_admin_role_sync.py` 驗證此掛接確實生效——resolve_role() 正確但沒接上登入流程等同沒有）修改 `backend/app/services/line_auth.py` 的 `upsert_user()`：在既有的 `display_name` / `picture_url` 更新之後、`db.flush()` 之前，加入 `user.role = resolve_role(identity.line_user_id)`。**必須是雙向同步**（名單內設 admin、名單外設 user），只升不降會讓 FR-007 失效。加註解說明「直接於資料庫授予 admin 會在下次登入被覆寫，授予一律走名單」。依賴 T012。
- [x] T014 [US1] 建立 `backend/app/api/v1/admin_session.py`：`router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])`，實作 `GET /admin/me` 回傳 `AdminSession`（`user_id`／`display_name`／`role`）。**權限依賴掛在 router 建構參數上，不寫在端點函式簽章**（[research.md R-02](./research.md#r-02權限檢查層的掛載方式)）。既有的 `require_admin()` 直接使用，不修改 `backend/app/core/deps.py`。
- [x] T015 [US1] 修改 `backend/app/main.py`：於既有的 `v1` router 上 `v1.include_router(admin_session.router)`。確認掛載位置在 catch-all 404 路由**之前**（該路由必須維持在所有 router 之後）。依賴 T014。
- [x] T016 [US1] 建立 `frontend/src/app/admin/layout.tsx`：呼叫 `GET /admin/me`，401／403 時 `router.replace('/dashboard')`；**在確認為管理員之前不得渲染任何後台內容**（不得閃現表格骨架、欄位名稱或功能標題，FR-017）。此檔案**刻意不放在 `(app)` 路由群組內**——該群組的 layout 會強制未建檔者導向 `/onboarding`，管理員多半未填健康檔案，放進去會被擋在後台外（[research.md R-10](./research.md#r-10前端後台的路由位置)）。不使用 `BottomNav`，不套用 `max-w-md` 手機寬度。
- [x] T017 [US1] 驗證 `frontend/src/components/ui/BottomNav.tsx` 與 `frontend/src/app/(app)/layout.tsx` **未被修改且不含任何指向 `/admin` 的連結**（FR-017、SC-003）。本輪不新增後台入口連結，管理員以直接輸入網址進入，此作法已記於 [quickstart.md](./quickstart.md)。

**Checkpoint**: US1 完成 → 權限邊界已成立，可獨立驗收。此時後台是空的，但安全價值已交付。

---

## Phase 4: User Story 2 — 管理員維護店家資料 (Priority: P2)

**Goal**: 管理員可於後台新增／編輯／刪除店家，座標為選填且須成對，未設座標者於清單明確標示。

**Independent Test**: 以管理員身分新增一家含完整資料的店家、修改其地址、再刪除，全程確認清單即時反映（quickstart 驗證 4）。不需要餐點功能存在。

### Tests for User Story 2 ⚠️

- [x] T018 [P] [US2] 建立 `backend/tests/integration/test_admin_stores.py`：涵蓋 CRUD 正常流程，以及四項邊界——名稱留空→422；**只填緯度不填經度→422**（FR-022）；**緯度填 91→422**（FR-023）；名稱與既有店家重複但地址不同→201 成功（FR-027）；對已刪除的店家執行編輯→404（FR-028）。

### Implementation for User Story 2

- [x] T019 [US2] 建立 `backend/app/schemas/admin.py`：`StoreInput`／`StorePatch`／`StoreOut`／`StoreWithCountOut`，欄位依 [contracts/admin-api.yaml](./contracts/admin-api.yaml)。以 pydantic `model_validator` 實作**座標成對驗證**——`StorePatch` 須以「套用更新後的最終狀態」判定，而非只看本次請求帶了哪些欄位（FR-022）。緯經度範圍以 `Field(ge=..., le=...)` 約束（FR-023）。錯誤訊息為可直接呈現的中文。
- [x] T020 [US2] 建立 `backend/app/services/admin_stores.py`（**檔名刻意不用 `stores.py`**——第二輪已規劃 `services/stores.py` 存放讀取查詢管線，同名會在合併時硬衝突）：實作 `list_stores()`（以 `LEFT OUTER JOIN + GROUP BY` 一次帶出每筆的 `menu_item_count`，[research.md R-08](./research.md#r-08刪除前如何取得將一併刪除的餐點數量)）、`get_store()`、`create_store()`、`update_store()`、`delete_store()`。查無資料一律 `raise AppError("NOT_FOUND")`。依賴 T005、T019。
- [x] T021 [US2] 建立 `backend/app/api/v1/admin_stores.py`：`APIRouter(prefix="/admin/stores", tags=["admin"], dependencies=[Depends(require_admin)])`，實作 `GET /`、`POST /`、`GET /{store_id}`、`PATCH /{store_id}`、`DELETE /{store_id}`（204 無回應體）。並於 `backend/app/main.py` 掛載。依賴 T020。
- [x] T022 [P] [US2] 在 `frontend/src/lib/api/types.ts` 新增 `Store`／`StoreWithCount`／`StoreInput` 型別，在 `frontend/src/lib/api/endpoints.ts` 新增 `adminApi.stores` 的 list／create／get／update／remove。路徑以 `/admin/stores...` 起始，沿用既有 `NEXT_PUBLIC_API_BASE_URL`（已含 `/api/v1`），**不新增第二個 base URL 環境變數**（[research.md R-01](./research.md#r-01管理端-api-的路由前綴)）。
- [x] T023 [US2] 建立 `frontend/src/app/admin/page.tsx`：以原生 `<table>` 呈現店家清單（名稱／地址／座標狀態／餐點數／操作），沿用既有 TanStack Query。**不引入任何 UI 元件庫、表格庫或表單庫**（[research.md R-13](./research.md#r-13後台介面的技術選擇)）。依賴 T016、T022。
- [x] T024 [US2] 建立 `frontend/src/components/admin/StoreForm.tsx`：名稱／地址／緯度／經度四個欄位的新增與編輯表單，以既有 `frontend/src/components/ui/Modal.tsx` 呈現。前端亦需擋下「只填單一座標值」，錯誤訊息與後端一致。
- [x] T025 [US2] 在店家清單實作**未設定座標的明確標示**（FR-025、SC-009）：`latitude` 為 null 的列顯示可一眼辨識的標記，並附說明「未設定座標，不會出現在使用者端的附近店家推薦中」。管理員無需開啟個別店家即可辨識待補資料。修改 `frontend/src/app/admin/page.tsx`。
- [x] T026 [US2] 在 `StoreForm.tsx` 的座標欄位旁加入固定提示文字（FR-026）：說明系統不驗證地址與座標是否一致、使用者端的距離計算一律以座標為準、地址僅供顯示。

**Checkpoint**: US1 + US2 皆可獨立運作。後台已能維護店家。

---

## Phase 5: User Story 3 — 管理員維護店家底下的餐點資料 (Priority: P3)

**Goal**: 管理員可在指定店家底下新增／編輯／刪除餐點；餐點必定歸屬於一家店家。

**Independent Test**: 在既有店家底下新增 3 道餐點、修改其中一道的熱量、刪除另一道，確認清單即時反映且其他店家的餐點不受影響（quickstart 驗證 5）。

### Tests for User Story 3 ⚠️

- [x] T027 [P] [US3] 在 `backend/tests/integration/test_admin_stores.py` 新增餐點區段：熱量填 -1→422（FR-032）；熱量填 0→201 成功且讀回為 `0`（FR-032 明確允許 0）；**熱量留空→201 成功且讀回為 `null` 而非 `0`**（FR-032 的不可逆性保護，若實作誤以 0 代替空值，此測試會失敗）；**只填熱量、三大營養素留空→201 成功**（四欄位彼此獨立，不比照座標的成對規則）；修改 A 店某餐點後 **B 店同名餐點數值不變**（FR-034）；於不存在的店家底下新增餐點→404 且不產生無主餐點（FR-035）；某店家的餐點清單**不含其他店家的餐點**（FR-033）。

### Implementation for User Story 3

- [x] T028 [US3] 在 `backend/app/schemas/admin.py` 新增 `MenuItemInput`／`MenuItemPatch`／`MenuItemOut`。欄位名稱**逐字沿用共用契約**（`calories`、`protein_g`、`carbs_g`、`fat_g`），**不加單位後綴**，即使第一輪的 `meal_items` 用的是 `calories_kcal`——契約優先於內部命名一致性。四項數值型別為 `Decimal | None = None` 且以 `Field(ge=0)` 約束（**T002 定案為選填**），`MenuItemInput.required` 只有 `name`。`MenuItemPatch` 須能區分「未提供該欄位＝維持原值」與「明確傳入 null＝改為未提供」，建議以 `model_fields_set` 判斷而非以值是否為 None 判斷。
- [x] T029 [US3] 在 `backend/app/services/admin_stores.py` 新增 `list_menu_items(store_id)`（須先確認店家存在，否則 `NOT_FOUND`）、`create_menu_item()`、`update_menu_item()`、`delete_menu_item()`。查詢一律以 `store_id` 收斂，不存在「查全部再過濾」的路徑。依賴 T006、T028。
- [x] T030 [US3] 建立 `backend/app/api/v1/admin_menu_items.py`：`APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])`，實作 `GET /admin/stores/{store_id}/menu-items`、`POST /admin/stores/{store_id}/menu-items`、`PATCH /admin/menu-items/{menu_item_id}`、`DELETE /admin/menu-items/{menu_item_id}`。編輯與刪除以餐點自身 id 定位，**不提供變更所屬店家的語意**。並於 `backend/app/main.py` 掛載。依賴 T029。
- [x] T031 [P] [US3] 在 `frontend/src/lib/api/types.ts` 與 `endpoints.ts` 新增 `MenuItem` 型別與 `adminApi.menuItems` 的 list／create／update／remove。
- [x] T032 [US3] 建立 `frontend/src/app/admin/stores/[storeId]/page.tsx`：該店家的餐點清單表格（名稱／熱量／蛋白質／碳水／脂肪／操作），並實作**尚無餐點時的空狀態**——顯示說明與新增操作，不得是空白畫面或錯誤（FR-036）。**營養數值為 `null` 時顯示為「未提供」（或 `—`），MUST NOT 顯示為 0**（FR-033）。依賴 T031。
- [x] T033 [US3] 建立 `frontend/src/components/admin/MenuItemForm.tsx`：名稱與四項營養數值的新增／編輯表單，前端擋下負數與非數字輸入，允許 0，**允許留空**。留空時送出 `null` 而非 `0`（FR-032）。表單須以提示文字明確告知管理員「留空＝店家未提供」與「填 0＝確實為 0」的語意不同。

**Checkpoint**: US1～US3 皆可獨立運作。後台已能完整維護店家與餐點。

---

## Phase 6: User Story 4 — 刪除店家時一併處理其底下的餐點 (Priority: P4)

**Goal**: 刪除有餐點的店家時，於執行前告知將一併刪除的餐點數並要求二次確認；確認後連帶刪除，取消則零變更。

**Independent Test**: 對一家有 3 道餐點的店家執行刪除，先取消一次確認資料完好，再確認一次確認店家與其全部餐點皆已移除且無殘留無主餐點（quickstart 驗證 6）。

### Tests for User Story 4 ⚠️

- [x] T034 [P] [US4] 在 `backend/tests/integration/test_admin_stores.py` 新增 **cascade 刪除**測試：建立一家含 3 道餐點的店家，刪除該店家後斷言 `SELECT count(*) FROM menu_items WHERE store_id = <已刪除 id>` 為 **0**（FR-040、SC-008）。**此測試必須跑在真 PostgreSQL 上**——`ON DELETE CASCADE` 是資料庫層行為，既有 conftest 的 testcontainers 方案已備妥。

### Implementation for User Story 4

- [x] T035 [P] [US4] 建立 `frontend/src/components/admin/ConfirmDialog.tsx`：通用的二次確認對話框，接受標題、說明文字與確認／取消回呼，沿用既有 `Modal.tsx`。
- [x] T036 [US4] 在 `frontend/src/app/admin/page.tsx` 的刪除流程接上 `ConfirmDialog`：確認訊息須依清單既有的 `menu_item_count` **明確告知將一併刪除 N 道餐點**（FR-038）；餐點數為 0 時改為說明沒有餐點會被一併刪除（US4 驗收情境 4）；選擇取消時**不得發出任何請求**（FR-039）。依賴 T023、T035。

**Checkpoint**: 全部 user story 完成，spec 的 4 個 story 皆可獨立驗收。

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 收尾與合併準備。tasks brief 明示介面視覺優化屬最低優先，故置於最後。

- [ ] T037 依 [quickstart.md](./quickstart.md) 的 6 項驗證情境逐項手動驗收，將結果記錄於本檔末的「執行紀錄」。
- [ ] T038 [P] 執行 `cd backend && ruff check . && ruff format --check .`，修正所有告警（line-length 100、既有 lint 規則）。
- [ ] T039 [P] 執行 `cd frontend && npm run lint`，修正所有告警。
- [ ] T040 契約一致性複查：逐欄比對 `backend/app/db/models/store.py`、`menu_item.py` 與 [reference/shared-schema-store-menu.md](../../reference/shared-schema-store-menu.md)，確認**欄位數量與名稱完全一致、零增減零更名**（SC-012）。若實作過程中曾偏離，須回頭修正或走契約修訂程序，不得默默保留。
- [ ] T041 產出合併前協調清單並知會第二輪開發者：本輪已建立 `0002` migration 與兩個 model；第二輪若也已產生建表 migration，須依 [plan.md](./plan.md)「與第二輪分支的合併風險」處理三項衝突（migration 雙 head、重複建表、model 檔衝突）。**此任務不代為執行合併，只負責知會與記錄。**
- [ ] T042 [P] 後台介面的視覺微調（**最低優先，可略過**）：僅在前述任務全數完成且有餘裕時進行。範圍限於基本可讀性（欄寬、間距、表單對齊）。**明確不做**：深色模式、行動版版面、動畫轉場、骨架屏、比照 `reference/prototype/caiuli.html` 的視覺風格（FR-045、FR-046）。

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（Setup）**：無前置依賴，立即可開始。**T002 阻塞 T008。**
- **Phase 2（Foundational）**：依賴 Phase 1 → 阻塞 US2／US3／US4
- **Phase 3（US1）**：只依賴 T003（設定），**不依賴 T005～T009 的建表**，急於取得 MVP 時可與 Phase 2 的建表任務並行
- **Phase 4（US2）**：依賴 Phase 2 完成 + T014／T016（router 與前端守衛的既有樣式）
- **Phase 5（US3）**：依賴 Phase 2 + US2 的店家資料存在（餐點需掛在店家底下）
- **Phase 6（US4）**：依賴 US2（刪除入口）+ US3（有餐點可連帶刪除）
- **Phase 7（Polish）**：依賴前述所有想交付的 story

### User Story Dependencies

- **US1（P1）**：完全獨立，不需要任何店家／餐點資料即可完整驗收 → **MVP**
- **US2（P2）**：需要 US1 的權限層與前端守衛已就緒
- **US3（P3）**：需要 US2 的店家存在（資料上的依賴，非程式碼依賴）
- **US4（P4）**：需要 US2 的刪除入口與 US3 的餐點資料

### Parallel Opportunities

- **Phase 2**：T003／T004／T005／T006 四項可完全平行（不同檔案）
- **Phase 3**：T010 與 T011 兩支測試檔可平行撰寫
- **Phase 4／5**：後端 schema→service→endpoint 為序列；但 T022／T031 的前端型別與 endpoints 可與後端平行進行（契約已於 [admin-api.yaml](./contracts/admin-api.yaml) 固定）
- **Phase 7**：T038／T039／T042 可平行

### Parallel Example: Phase 2

```bash
# 四個檔案互不相干，可同時進行：
Task: "在 backend/app/core/config.py 新增 admin_line_user_ids 設定"
Task: "在 backend/.env.example 補上 ADMIN_LINE_USER_IDS"
Task: "建立 backend/app/db/models/store.py"
Task: "建立 backend/app/db/models/menu_item.py"
```

---

## Implementation Strategy

### MVP First（僅 User Story 1）

1. Phase 1：確認建表現況與三項契約決議（T001～T002）
2. Phase 2：至少完成 T003（US1 只需要這一項設定）
3. Phase 3：完成 US1 全部任務
4. **STOP and VALIDATE**：執行 quickstart 驗證 1～3，特別是驗證 3 的 10 支端點 403 一致性
5. 此時後台是空的，但**憲章原則 IV 的安全邊界已完整成立並可驗收**——這正是 US1 被列為 P1 的原因

### Incremental Delivery

1. Setup + Foundational → 資料表與設定就緒
2. + US1 → 權限邊界成立（**MVP**，可獨立展示）
3. + US2 → 可維護店家，第二輪已能讀到真實店家資料
4. + US3 → 可維護餐點，第二輪的餐點瀏覽有資料可用
5. + US4 → 刪除流程完備，無孤兒資料風險

> US2 完成後，第二輪的讀取端即可開始以真實資料驗證，不必等到本輪全部完成。

### 安全性驗收的獨立性（tasks brief 明確要求）

「一般使用者存取管理端 API 被拒絕」由 **T011** 獨立成檔承載（`test_admin_access_control.py`），**不散落在各 CRUD 任務中**。這讓該項可單獨執行與驗收：

```bash
pytest backend/tests/integration/test_admin_access_control.py -v
```

每新增一支管理端端點，都須回到 T011 的清單補上對應斷言——這是驗證 [research.md R-02](./research.md#r-02權限檢查層的掛載方式) 「router 層掛載」是否確實生效的唯一自動化手段。

---

## 邊界情境的任務對應（tasks brief 明確要求確認）

| spec 的邊界情境 | 對應任務 | 驗收依據 |
|----------------|---------|---------|
| 座標選填、未填時允許儲存 | T005（CHECK 允許 null）、T019（schema）、T018（測試） | FR-021 |
| 座標須成對，只填一個要擋 | T005（`ck_stores_coords_paired`）、T019（`model_validator`）、T024（前端）、T018（測試） | FR-022 |
| 座標範圍 -90～90／-180～180 | T005（CHECK）、T019（`Field(ge, le)`）、T018（測試） | FR-023 |
| 未設座標者於清單明確標示 | **T025（專屬任務）** | FR-025、SC-009 |
| 地址與座標不一致的告知 | **T026（專屬任務）** | FR-026 |
| cascade delete 的資料庫行為 | T006／T008（`ondelete="CASCADE"`）、**T034（專屬測試）** | FR-037、FR-040、SC-008 |
| 刪除前告知餐點數並二次確認 | T020（`menu_item_count`）、**T036（專屬任務）** | FR-038 |
| 取消刪除時零變更 | T036 | FR-039 |
| 營養數值允許 0、拒絕負數 | T028（schema）、T006（CHECK）、T027（測試） | FR-032 |
| 營養數值可留空，且留空 ≠ 0 | T006（nullable）、T028（schema）、T033（表單提示）、**T027（測試斷言讀回為 null 而非 0）** | FR-032 |
| 清單須區分「未提供」與「0」 | **T032（專屬呈現規則）** | FR-033 |
| 一般使用者存取管理端被拒 | **T011（獨立測試檔）** | FR-014、FR-015、SC-001、SC-002 |
| 未登入者回 401 而非 403 | T011 | FR-016 |
| 一般使用者看不到後台入口 | T016、**T017（專屬驗證任務）** | FR-017、SC-003 |
| 對已刪除的店家操作回 404 | T020（`NOT_FOUND`）、T018（測試） | FR-028 |
| 店家名稱可重複 | T005（不加 UNIQUE）、T018（測試） | FR-027 |

---

## Notes

- `[P]` 任務＝不同檔案、無未完成依賴
- 每個 story 皆可獨立完成與驗收；可在任一 Checkpoint 停下驗證
- **測試先寫並確認失敗，再進行實作**
- 建議每個任務或每個邏輯群組完成後即 commit
- ⚠️ 實作 T006 時務必確認 `MenuItem`（本輪，店家菜單）與既有 `MealItem`（第一輪，使用者飲食紀錄品項）的 import 沒有取錯——兩者只差兩個字母且語意完全不同
- ⚠️ T013 完成後，**直接於資料庫把 role 改成 admin 將無效**（下次登入會被名單覆寫）。授予一律走名單，資料庫直改僅能作為緊急撤銷，且撤銷後必須同步移出名單，見 [quickstart.md](./quickstart.md) 第 3 節

---

## 執行紀錄

> 供 T001、T037 等需要記錄結論的任務填寫。

| 任務 | 日期 | 結論 |
|------|------|------|
| T001 | 2026-08-04（預查） | `main`／`round2`／`round3` 三分支皆只有 `0001` migration，無店家／餐點 model；第二輪僅完成 specify + plan 未 implement。**本輪需要建表。** 實作開跑時仍須重跑確認。 |
| T001 | 2026-08-04（implement 前重跑，含 `git fetch`） | 結論不變：三分支仍只有 `20260803_0001_initial_schema.py`，且 `0001` 的 docstring 已明載其未建立任何店家／餐點資料表；`backend/app/db/models/` 無 `store.py`／`menu_item.py`。**確認本輪需新建 migration（T008，US2 範圍）**。 |
| T002 | 2026-08-04 | 三項全數定案：主鍵 **UUID**（雙方一致）；四個營養欄位 **nullable**（採納第二輪 OQ-2b 主張，本輪由 NOT NULL 改為可空）；`name` 用 **`VARCHAR(255)`**（從第一輪慣例，對讀取端無影響）。結論已同步回共用契約檔，spec／data-model／contracts 亦已連帶更新。**T008 的阻塞已解除。** |
| US1 驗收 | 2026-08-04 | **通過。** 自動化：98 passed / 0 skipped（真 PostgreSQL），其中安全性 8 項 + 名單核對 15 項 + 登入角色同步 6 項；並以突變測試確認「拿掉權限保護時測試會失敗」。實機：後端 API 四項全對（管理員 200／一般使用者 403／未登入 401／一般使用者打一般 API 200，證明其 token 有效）；瀏覽器守衛情境 A～D 全對，**導離過程未閃現任何後台畫面**（FR-017）。前端 typecheck／lint／build／vitest 全綠。 |
| US2 驗收 | 2026-08-04 | **通過。** 139 passed（真 PostgreSQL）。migration 0002 已套用，schema 與 data-model.md 逐欄一致（3 條座標 CHECK、4 條營養 CHECK、FK CASCADE、ix_menu_items_store）。實機驗證：建立含／不含座標店家皆 201、清單帶 menu_item_count、一般使用者存取店家 API 403、透過 API 刪除店家後殘留餐點數為 0。前端 typecheck／lint／build 全綠。 |
| US3 驗收 | 2026-08-04 | **通過。** 172 passed（真 PostgreSQL），其中安全測試 35 項涵蓋契約定義的全部 10 支端點。實機驗證：只填熱量→其餘欄位為 null 而非 0；零卡飲料→calories/fat_g 存為 0 且 protein_g 仍為 null（NULL 與 0 可區分）；負數→422 附可讀訊息；不存在的店家底下新增→404 且不產生孤兒餐點。前端 typecheck／lint／build／vitest 全綠。 |
| T037 | | |
