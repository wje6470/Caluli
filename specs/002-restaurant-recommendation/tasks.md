---

description: "Task list for 推薦餐廳（第二輪）"
---

# Tasks: 推薦餐廳（第二輪）

**Input**: Design documents from `/specs/002-restaurant-recommendation/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/openapi.yaml](./contracts/openapi.yaml)、[quickstart.md](./quickstart.md)

**補充依據**: [reference/round2-tasks-brief.md](../../reference/round2-tasks-brief.md)（任務排序）、2026-08-04 第三輪交接說明（共用契約語意）

**Tests**: 本輪**納入測試**。這不是選配——[憲章](../../.specify/memory/constitution.md)「開發流程與品質門檻」明定「涉及登入、權限或**營養資料表**的變更必須具備對應測試」，而本輪正是新增一組營養資料表（店家餐點營養值）。測試範圍依 [research.md](./research.md) R-11 的對應表，集中於：距離計算與排序管線（數值正確性無法靠肉眼驗證）、`null` vs `0` 的雙向區分（最易寫錯且錯了不會報錯）、資料表分離稽核、以及三種空狀態的可區分性。UI 樣式不強制測試。

**Organization**: 任務依 user story 分組以支援獨立實作與驗收。

## 排序說明（依 tasks-brief 指定調整）

brief 指定的排序與嚴格 MVP-first 有一處差異，此處明列以免實作時誤判：

| brief 指定 | 落在本清單的位置 |
|---|---|
| ① migration → ② seed → ③ 距離運算核心 | Phase 2（全部後端、不含 UI） |
| ④ 定位權限請求與**拒絕時的替代方案** | Phase 3（US1 內） |
| ⑤ 店家清單／餐點瀏覽 UI | Phase 3（清單）、Phase 4（餐點） |
| ⑥ 空狀態、**定位失敗**等邊界畫面（較後） | Phase 5（US3） |
| ⑦ LIFF 入口限定判斷（較後） | Phase 6 |

⚠️ **兩點後果，請先理解再開工**：

1. **US3 的第 1 個驗收情境（拒絕授權 → 退回全部店家清單，FR-008）在 Phase 3 就交付**，不等到 Phase 5。理由是使用者隨時可能按下「拒絕」，US1 若沒有這條分支就不是可出貨的狀態。Phase 5 承接的是 US3 的**其餘**情境：定位服務失敗（與拒絕不同文案）、逾時、重試、以及三種空狀態。
2. **Phase 6 的 LIFF 入口限定排在最後，代表 Phase 3–5 期間 `/restaurants` 在一般瀏覽器也看得到**。這是 brief 認可的暫時狀態（「先把核心功能在 LIFF 環境跑通再處理入口限制」），但 **FR-001〜FR-003 未完成前不可視為本輪完成**，SC-006 也還不成立。

若你更想要嚴格的故事完整性，把 Phase 6 併入 Phase 3 即可，任務內容不需改動。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行執行（不同檔案、無未完成的相依）
- **[Story]**: 對應的 user story（US1／US2／US3）
- 描述含確切檔案路徑與對應的 FR／驗收情境

## Path Conventions

Web app 結構，沿用第一輪：`backend/app/`、`frontend/src/`。本輪為純增量，不移動既有檔案。

---

## Phase 1: Setup（含建表前的人工確認閘）

**Purpose**: 解除建表前的阻塞決策，並備妥可調參數

- [X] T001 ✅ **已由 2026-08-04 第三輪執行清單結案**（無需再確認）：主鍵 **UUID**、營養欄位 **nullable**（且對方有測試斷言 NULL 不會被寫成 0），皆與本輪建議一致；另補足 `address` VARCHAR(500) **NOT NULL**、`name` VARCHAR(255) 不唯一、經緯度以 DB CHECK 保證成對。結論已回填 [research.md](./research.md) 的「已結案」表。**建表歸屬亦已定為第三輪**，故 T005 改為「刪除本輪 migration」。原任務描述如下：**【人工，阻塞 T005】** 與第三輪（`feature/round3-admin`）確認兩項未定案的契約細節，並把結論回填至 [research.md](./research.md) 的 Open Questions 表：**(a) OQ-1 主鍵型別**——本輪建議 UUID（與第一輪全專案一致），UUID 與 BIGSERIAL 的差異無法靠改欄位名補救，需一方重建資料表；**(b) OQ-2b 四個營養欄位是否允許 NULL**——本輪建議 nullable，這是 FR-025「無資料」呈現的前提，若設 NOT NULL 則該需求在資料層即不可能實現。⚠️ 依 2026-08-04 交接說明，資料表「由先合併回 main 的一方建立」，**先建表者等於替雙方定案**，故此確認必須早於 T005。
- [X] T002 於 `backend/app/core/config.py` 的 `Settings` 新增兩個常數：`nearby_radius_km: float = 5.0`（FR-020）與 `nearby_limit: int = 10`（FR-014），並加註「暫定值，實地測試後可調（OQ-7）」。集中於此的理由見 [research.md](./research.md) R-04——半徑值散落多處會使日後調整漏改。

---

## Phase 2: Foundational（阻塞所有 user story）

**Purpose**: 資料表、測試資料與距離運算核心。此階段全為後端、不含任何 UI，可完全以 pytest 驗證。

**⚠️ CRITICAL**: 本階段完成前，任何 user story 都無法開始

### 資料層

- [X] T003 ⚠️ **組織方式已變更（2026-08-04 第三輪執行清單）**：改為與第三輪相同的拆檔方式——`backend/app/db/models/store.py`（`Store`）＋ `backend/app/db/models/menu_item.py`（`MenuItem`），欄位逐項比照其最終定義。**合併時直接採用第三輪版本**，本輪查詢程式碼零改動（依賴的是 `from app.db.models import Store, MenuItem` 這個對方保證穩定的匯入介面）。本輪保留鏡像而非直接刪除，是為了讓分支在合併前仍能執行測試與 seed。原任務描述如下：於 `backend/app/db/models/store.py` 建立 `Store` 與 `MenuItem` 兩個 model（**刻意同檔**，理由見 [plan.md](./plan.md) Structure Decision：縮小與第三輪的合併衝突面，並避免與既有 `meal_item.py` 混淆）。欄位**完全依共用契約**，不得增減或改名——`stores`(id, name, address, latitude, longitude, created_at, updated_at)、`menu_items`(id, store_id, name, calories, protein_g, carbs_g, fat_g, created_at, updated_at)。關鍵約束依 [data-model.md](./data-model.md)：`latitude`／`longitude` **nullable**（後台允許暫不填座標，屬常態資料）、四個營養欄位 **nullable**（FR-025 前提）且 CHECK `>= 0`、`menu_items.store_id` 外鍵 **ON DELETE CASCADE**、`name` 欄位 **NOT NULL 但不設 UNIQUE**（連鎖分店同名為正常資料，FR-016a）。沿用第一輪的 `Base`／`TimestampMixin`／`uuid_pk()`。
- [X] T004 於 `backend/app/db/models/__init__.py` 匯出 `Store`、`MenuItem` 並加入 `__all__`，使 Alembic autogenerate 掃描得到。
- [X] T005 ⚠️ **範圍已變更（2026-08-04 第三輪執行清單）：本輪不建立 migration**。DDL 由第三輪的 `20260804_0002_stores_menu_items.py` 提供——他們負責寫入，由寫入方持有 schema 是正確歸屬；兩支同為 `0002` 且同以 `0001` 為 parent 會造成 Alembic 雙 head 與重複建表。本輪原建立的 `20260804_0002_store_menu.py` **已刪除**。本機開發改由 `Base.metadata.create_all()` 建表（`conftest.py` 本就如此，測試不受影響）。原任務描述如下：建立 migration `backend/alembic/versions/20260804_0002_store_menu.py`（`revision = "0002"`、`down_revision = "0001"`）。`upgrade()` **只做兩個 `create_table`，不得有任何 `alter_table`**（FR-032：不修改第一輪既有資料表）；`downgrade()` 反序 `drop_table`。比照第一輪 `0001` 的作法，在 docstring 中留下**憲章原則 V 稽核紀錄**：本 migration 未與 `food_nutrition_references` 建立任何方向的外鍵、未合併資料表、未以型別欄位混存兩類營養資料。
  > ⚠️ **合併前人工檢查項（不需 agent 處理，僅記錄）**：本輪與第三輪在不同分支上共用這兩張表，且依 2026-08-04 交接說明「由先合併回 `main` 的一方建立」。合併回 `main` 前**必須人工確認**：(1) 兩分支是否都產生了建立這兩張表的 migration——若是，會有兩個 revision 同時以 `0001` 為 parent，Alembic 出現雙 head 且嘗試重複建表；(2) 版本號 `0002` 是否與第三輪的 migration 撞號；(3) 欄位型別與 nullability 是否與對方一致（見 T001）。處理方向：保留先合併一方的 migration，後者刪除自己的並核對 model，必要時以 `alembic merge` 建立匯合點。**本檔案設計為可捨棄**——若第三輪先合併，刪除本檔並確認 `store.py` 的 model 與其結構一致即可。
- [X] T006 執行 `alembic upgrade head` 於本機資料庫，確認兩張表建立成功且欄位、nullability、外鍵行為與 [data-model.md](./data-model.md) 一致（特別確認 `ON DELETE CASCADE`：刪除一筆 store 後其 menu_items 一併消失）。

### 測試資料（brief 排序 ②）

- [X] T007 建立 `backend/app/scripts/seed_stores.py`，以模組內字面值定義測試資料（**不放進 migration**，理由見 [research.md](./research.md) R-09：migration 會在每個環境自動執行，假資料將自動進入正式資料庫且無欄位可供區分）。主鍵以 `uuid5` 從固定命名空間推導，推導鍵為 `f"{店名}|{地址}"`（店家）與 `f"{店家UUID}|{索引}|{餐點名}"`（餐點）——**不可只用名稱**，因為名稱不具唯一性。重複執行為 upsert 而非重複插入。測試資料一律以 **`[測試]` 店名前綴**標示（FR-035；契約無可標記的欄位，且本輪不得增欄位）。
- [X] T008 於 `seed_stores.py` 補上 `--purge` 參數，以 `name LIKE '[測試]%'` 精準刪除測試店家（餐點由 CASCADE 連帶刪除），確認正式資料不受影響。
- [X] T009 依 [quickstart.md](./quickstart.md)「測試資料的組成」填入資料，以台北車站 `(25.0478, 121.5170)` 為參考點。**每一組都對應一個驗收情境，缺一項就有情境驗不到**：5 公里內 12 家（>10 筆才驗得到截斷，FR-014）、5 公里外 2 家（淡水、基隆，驗半徑排除與「改看全部店家」，FR-019／FR-020）、座標留空 1 家（驗 FR-018 排除於排序但出現於全部清單）、**同名不同址的連鎖分店 2 家**（驗 FR-016a）、餐點 ≥8 筆 1 家（驗捲動）、餐點 0 筆 1 家（驗 FR-024）、四欄營養皆 NULL 的餐點 ≥1 筆（驗「無資料」）、**營養值確實為 0 的餐點 ≥1 筆**（驗 0 顯示為 0，FR-025 後半）、同店同名餐點 2 筆（驗不去重）。
- [X] T010 執行 `python -m app.scripts.seed_stores` 並以 SQL 確認資料筆數與分佈符合 T009，再執行第二次確認為 upsert（總筆數不變），最後執行 `--purge` 確認清除乾淨後重新載入。

### 距離運算核心（brief 排序 ③）

- [X] T011 [P] 建立 `backend/app/services/geo.py`，實作 `haversine_km(lat1, lng1, lat2, lng2) -> float` 純函式，地球半徑取 6371.0088 km。**必須是不依賴資料庫與 ORM 的純函式**——這是 [research.md](./research.md) R-01 選擇應用層計算而非 SQL 內嵌的決定性理由，若在此引入 Session 依賴等於放棄該決策的全部收益。
- [X] T012 [P] 建立 `backend/tests/unit/test_geo.py`：同點距離為 0、已知兩點距離（如台北車站↔淡水約 20 km）誤差在容許範圍內、跨經度換日線（±180 附近）不出現異常大值、極值座標（±90 緯度）不拋例外。

**Checkpoint**: 資料表、測試資料、距離公式皆就緒且可獨立驗證，user story 可開始

---

## Phase 3: User Story 1 - 授權定位並看到附近最近的店家 (Priority: P1) 🎯 MVP

**Goal**: 使用者在 LIFF 內進入推薦餐廳、授權定位後，看到 5 公里內依距離排序的最近 10 家店家；若使用者拒絕授權，退回顯示全部店家清單而非中斷。

**Independent Test**: 以 DevTools Sensors 將定位設為台北車站座標，走「進入推薦餐廳 → 允許定位 → 看到 10 筆依距離排序的清單」；再以拒絕權限走一次，確認退回全部清單。對應 [quickstart.md](./quickstart.md) V1、V2、V4。

### 後端：查詢管線與端點

- [X] T013 [US1] 建立 `backend/app/schemas/store.py`：`StoreOut`（含 `distance_m: int | None`）、`StoreListResponse`（含 `mode`、`radius_km`、`total_store_count`、`stores`）、`MenuItemOut`（四個營養欄位皆 `Decimal | None`）、`MenuItemListResponse`，欄位與 [contracts/openapi.yaml](./contracts/openapi.yaml) 完全對齊。⚠️ `calories` 資料表欄位在 API 回應中命名為 `calories_kcal`（沿用第一輪慣例），此映射需在 schema 中明確處理。
- [X] T014 [US1] 建立 `backend/app/services/stores.py`，實作 `list_stores(db, lat, lng)` 查詢管線。**順序固定且不可調換**（[data-model.md](./data-model.md)「查詢管線」）：取出全部 stores → 排除 `latitude` 或 `longitude` 為 NULL 者（FR-018）→ 逐筆算 haversine → 過濾 > `nearby_radius_km`（FR-020）→ 依距離升冪排序 → 取前 `nearby_limit` 筆（FR-014）→ 附上 `total_store_count`（步驟一的總筆數，**未經任何過濾**，FR-019／R-05）。無座標時走全部模式：僅取全部 + 依 `name` 升冪 + `distance_m` 一律 `None`（FR-017）。⚠️ **不得加任何「排除已刪除」的過濾條件**——資料表無軟刪除欄位，刪除為實刪除（FR-018a）。
- [X] T015 [P] [US1] 建立 `backend/tests/unit/test_stores_query.py`，逐條驗證管線順序（這些是本輪最容易寫錯且錯了不會報錯的地方）：**(a)** 座標為 NULL 的店家不出現在附近模式結果中，且不被當作 (0,0) 排到最前；**(b)** 半徑邊界——恰好 5.0 km 的店家納入、5.01 km 排除；**(c)** 5 公里內 12 家時只回 10 筆；**(d)** 5 公里內僅 3 家時回 3 筆，**不以範圍外的店家補足至 10 筆**（FR-020 明文禁止）；**(e)** 排序正確——每筆距離皆不大於下一筆（SC-002）；**(f)** `total_store_count` 不受半徑、筆數上限與座標有效性影響。
- [X] T016 [US1] 建立 `backend/app/api/v1/stores.py`，實作 `GET /stores`（`lat`／`lng` 皆為選填，同時提供則走附近模式，同時省略則走全部模式）。**`lat` 與 `lng` 只給其一必須回 `VALIDATION_ERROR` 422**，不得無聲退回全部模式（R-06：否則前端會誤以為使用者位置已納入計算）。以 Pydantic 驗證 `lat ∈ [-90, 90]`、`lng ∈ [-180, 180]`（R-07）。掛載第一輪既有的 `CurrentUser` 依賴要求登入（FR-004，不分岔驗證邏輯）。⚠️ **本檔案只能有 GET**，不得建立或預留任何寫入端點（FR-029，屬第三輪範圍）。
- [X] T017 [US1] 於 `backend/app/main.py` 的 `v1` router 註冊 `stores.router`（追加一行 `v1.include_router(stores.router)`，不調整既有註冊順序）。
- [X] T018 [P] [US1] 建立 `backend/tests/integration/test_stores_api.py` 涵蓋附近模式：授權後回傳筆數 ≤ 10、排序正確、`mode == "nearby"`、`radius_km == 5`；未帶 token 回 401（FR-004）；只給 `lat` 不給 `lng` 回 422。

### 前端：定位取得與清單畫面（brief 排序 ④⑤）

- [X] T019 [P] [US1] 於 `frontend/src/lib/api/types.ts` 新增 `Store`、`MenuItem`、`StoreListResponse`、`MenuItemListResponse` 型別，與 [contracts/openapi.yaml](./contracts/openapi.yaml) 對齊；四個營養欄位型別為 `number | null`（**不可寫成 `number`**，否則 TypeScript 會讓「無資料」分支看起來不可能發生）。
- [X] T020 [P] [US1] 於 `frontend/src/lib/api/endpoints.ts` 新增 `storeApi.list(lat?, lng?)`，沿用既有 `api.get` 與錯誤處理慣例。
- [X] T021 [US1] 建立 `frontend/src/lib/geo/location.ts`，封裝 `navigator.geolocation.getCurrentPosition`，回傳可辨識聯集 `{ status: 'granted', coords } | { status: 'denied' } | { status: 'unavailable', reason }`。本階段**至少**正確處理 `PERMISSION_DENIED (code 1) → 'denied'`（FR-008）；`code 2/3` 先一併映射為 `'unavailable'`，於 Phase 5 細分逾時與訊號問題。`timeout: 10000` 對應 FR-010。⚠️ 第一輪**沒有**可重用的權限元件（相機走 `<input capture>`，由作業系統處理，偵測不到拒絕），故本檔案為全新實作，見 [research.md](./research.md) R-02。
- [X] T022 [P] [US1] 建立 `frontend/tests/unit/location.test.ts`，以 stub 的 `GeolocationPositionError` 驗證 `code 1 → 'denied'`、`code 2 → 'unavailable'`、`code 3 → 'unavailable'`、成功 → `'granted'` 且帶座標。這是 FR-007「拒絕與失敗必須分開處理」的唯一分歧點，映射錯了整條降級路徑都會走錯畫面。
- [X] T023 [US1] 建立 `frontend/src/hooks/useCurrentLocation.ts`，以 `useQuery({ queryKey: ['geolocation'], staleTime: Infinity, retry: false })` 封裝 T021。**`retry: false` 是必要的**——自動重試會讓畫面卡在載入並重複彈出權限提示，而 FR-009 要求的是使用者主動觸發的重試。以 query cache 承載座標可同時滿足 FR-026（返回不重取）與 US1-7（重載才重取），見 [research.md](./research.md) R-10。
- [X] T024 [P] [US1] 建立 `frontend/src/lib/format/distance.ts`，1 公里以下顯示公尺、以上顯示公里；附 `frontend/tests/unit/distance.test.ts`。
- [X] T025 [P] [US1] 建立 `frontend/src/components/restaurants/StoreCard.tsx`，顯示店名、**地址**與距離（距離於全部模式下不顯示）。⚠️ 地址是必要欄位而非裝飾——店名不唯一（連鎖分店同名），缺少地址使用者無法辨別是哪一家分店（FR-016）。
- [X] T026 [US1] 建立 `frontend/src/app/(app)/restaurants/page.tsx`，串接 `useCurrentLocation` 與 `storeApi.list`：授權成功 → 帶座標查詢並呈現排序清單（FR-014、FR-016）；**授權被拒 → 以不帶座標的查詢呈現全部店家清單，不排序、不顯示距離，並顯示重新開啟權限的說明**（FR-008、US3-1，依 brief 排序④提前至此）。清單項目的 React key 與路由參數**一律使用 `id`，不得使用 `name`**（FR-016a：同名分店會造成 key 重複與渲染錯亂）。
- [X] T027 [US1] 於 `frontend/src/components/ui/BottomNav.tsx` 的 `TABS` 新增「找餐廳」分頁指向 `/restaurants`。**本階段先無條件顯示**，LIFF 入口限定於 Phase 6 處理（brief 指定較後）。
- [X] T028 [US1] 依 [quickstart.md](./quickstart.md) V1、V2、V4 手動驗證：台北車站座標 → 恰 10 筆且座標留空的那家**不在**清單中；淡水座標 → 只出現該區 1 家且**不以台北的店家補足**；拒絕權限 → 全部清單且座標留空的那家**出現在**清單中。

**Checkpoint**: US1 可獨立展示——授權與拒絕兩條路徑都能看到店家清單

---

## Phase 4: User Story 2 - 瀏覽店家餐點的熱量與營養素 (Priority: P2)

**Goal**: 使用者點選店家後可瀏覽該店餐點清單，每項顯示熱量與三大營養素，並可返回清單改看其他店家。

**Independent Test**: 在已 seed 的資料上點選餐點 ≥8 筆的店家，確認逐項顯示名稱與四項營養值且與資料庫一致；再點選餐點 0 筆的店家確認空狀態。對應 [quickstart.md](./quickstart.md) V7、V7b、V8。

### 後端

- [X] T029 [US2] 於 `backend/app/services/stores.py` 新增 `get_store(db, store_id)` 與 `list_menu_items(db, store_id)`；店家不存在時拋 `AppError("NOT_FOUND")`（FR-027）。⚠️ **不得 import 任何第一輪的營養相關模組**（`food_reference`、`nutrition` 等）——營養值一律取自 `menu_items`，即使餐點名稱與通用對照表相同也不查詢、不連動（憲章原則 V、FR-030、FR-031）。
- [X] T030 [US2] 於 `backend/app/api/v1/stores.py` 新增 `GET /stores/{store_id}` 與 `GET /stores/{store_id}/menu-items`，兩者皆在店家不存在時回 404。營養欄位**原樣回傳 `null` 與 `0`，不做任何正規化**（FR-025）。同樣只能有 GET。
- [X] T031 [P] [US2] 於 `backend/tests/integration/test_stores_api.py` 補上：不存在的 `store_id` 回 404（FR-027）；餐點 0 筆的店家回 `{"menu_items": []}` 且為 **200 而非 404**（空清單是正常結果，不是錯誤，FR-024）；含 NULL 營養欄位的餐點回應中該欄位為 `null` **而非 0**；營養值為 0 的餐點回應中為 `0` **而非 null**（FR-025 雙向）。

### 前端

- [X] T032 [US2] 於 `frontend/src/lib/api/endpoints.ts` 新增 `storeApi.get(storeId)` 與 `storeApi.menuItems(storeId)`。
- [X] T033 [US2] 建立 `frontend/src/components/restaurants/MenuItemRow.tsx`，顯示餐點名稱、熱量與蛋白質／碳水／脂肪。⚠️ **`null` 與 `0` 必須雙向區分**：`null` → 「無資料」、`0` → `0`（FR-025）。**必須以 `=== null` 明確判斷**——`0` 是 falsy，`value or '無資料'`、`value ? fmt(value) : '無資料'`、`{value && ...}` 都會把 0 誤顯示為「無資料」，這是本輪最容易寫錯的一行且不會拋任何錯誤。
- [X] T034 [P] [US2] 建立 `frontend/tests/unit/menu-item.test.tsx`，斷言四個營養欄位在 `null` 時顯示「無資料」、在 `0` 時顯示 `0`。這支測試存在的唯一理由就是抓 T033 的 falsy 誤判。
- [X] T035 [US2] 建立 `frontend/src/app/(app)/restaurants/[storeId]/page.tsx`，顯示店名與餐點清單，長清單可捲動（US2-2）。餐點的 React key 使用 `id`——同店家內允許同名餐點，不得去重（FR-016a）。
- [X] T036 [US2] 於 `frontend/src/app/(app)/restaurants/[storeId]/page.tsx` 加入「此店家尚未提供餐點資訊」的空狀態與返回操作（FR-024），以及店家不存在（404）時的「此店家已不存在」說明與返回清單操作（FR-027）。兩者皆**不得**呈現空白或無法離開的錯誤畫面。
- [X] T037 [US2] 驗證 `frontend/src/app/(app)/restaurants/[storeId]/page.tsx` 返回 `frontend/src/app/(app)/restaurants/page.tsx` 的行為：清單**維持原排序**且**不重新請求定位權限**（FR-026、US2-4）。此行為由 T023 的 query cache 承載——若實作時把座標改放元件 state 或 `sessionStorage`，此項會失敗（前者返回時重新請求權限，後者重載時沿用舊座標而違反 US1-7）。
- [X] T038 [US2] 依 [quickstart.md](./quickstart.md) V7、V7b、V8 手動驗證：含 NULL 的餐點顯示「無資料」且值為 0 的餐點顯示 `0`；同店同名的兩筆餐點各自列出未被去重；兩家同名分店各自列出、以地址區分、分別點入不互串。

**Checkpoint**: US1 與 US2 皆可獨立運作——找得到店家，也看得到餐點營養

---

## Phase 5: User Story 3 - 定位不可用時仍可瀏覽店家（其餘降級路徑） (Priority: P3)

**Goal**: 定位服務失敗（裝置定位關閉、GPS 訊號問題、逾時）時，以**與拒絕授權不同的說明**退回全部店家清單並提供重試；三種空狀態各自可區分。

> **範圍說明**：US3 的第 1 個驗收情境（拒絕授權 → 全部清單）已於 T026 交付（brief 排序④）。本階段承接其餘情境：US3-2（定位失敗、不同文案、可重試）、US3-3（重試成功切換）、US3-5（資料庫無店家）、以及 FR-019 的「附近查無店家」。

**Independent Test**: 以 DevTools Sensors 設為 "Location unavailable" 進入，確認文案與 V4 的拒絕文案明顯不同且出現「重試定位」；改回台北車站座標後點重試，確認切換為排序清單。對應 [quickstart.md](./quickstart.md) V3、V5、V6。

- [X] T039 [US3] 建立 `frontend/src/components/ui/PermissionNotice.tsx` 呈現層共用元件（圖示＋標題＋說明＋主要動作＋次要動作）。這是 [research.md](./research.md) R-02 評估後**唯一可與第一輪相機權限共用的層**——取得機制（file input vs geolocation API）無共同抽象，不強行統一。第一輪 `capture/page.tsx` 改用此元件屬**可選後續改善，不在本輪範圍**（已驗收流程不為形式一致承擔回歸風險）。
- [X] T040 [US3] 於 `frontend/src/lib/geo/location.ts` 細分 `code 2 POSITION_UNAVAILABLE` 與 `code 3 TIMEOUT` 的 `reason`，並新增座標有效性檢查——超出 `lat ∈ [-90,90]`／`lng ∈ [-180,180]` 時**不呼叫 API**，直接視為定位失敗（R-07：送給後端只會得到通用 API 錯誤，而非帶重試按鈕的定位失敗畫面）。同步更新 `frontend/tests/unit/location.test.ts`。
- [X] T041 [US3] 建立 `frontend/src/components/restaurants/states.tsx`，含四種**彼此可區分**的畫面（SC-004、SC-005）：`LocationDeniedNotice`（指向**權限設定**，無重試按鈕）、`LocationUnavailableNotice`（指向**裝置定位設定／訊號**，**有**「重試定位」按鈕）、`NoNearbyStores`（「附近查無店家」＋「改看全部店家」操作）、`NoStoresAtAll`（「目前尚無店家資料」，**不提供**改看操作——那只會導向另一個空清單）。
- [X] T042 [US3] 於 `frontend/src/app/(app)/restaurants/page.tsx` 接上定位失敗分支：顯示 `LocationUnavailableNotice` **並同時呈現全部店家清單**（FR-009），重試成功後畫面切換為排序清單且**不需重新整理頁面**（FR-011、US3-3）。將 T026 的拒絕分支改用 `LocationDeniedNotice` 以統一呈現。
- [X] T043 [US3] 於 `frontend/src/app/(app)/restaurants/page.tsx` 接上空狀態判斷，**依 `total_store_count` 區分**（R-05）：`stores` 為空且 `total_store_count > 0` → `NoNearbyStores`；`stores` 為空且 `total_store_count == 0` → `NoStoresAtAll`。⚠️ 只看 `stores: []` 無法分辨這兩者，而它們的文案與可用操作完全不同。「改看全部店家」的行為是以不帶座標的查詢重新取得清單（FR-019）。
- [X] T044 [P] [US3] 於 `backend/tests/integration/test_stores_api.py` 補上三種空狀態的回應斷言：有店家但全在 5 公里外 → `stores: []` 且 `total_store_count > 0`；資料庫無店家 → `stores: []` 且 `total_store_count == 0`；全部模式 → `mode == "all"`、`radius_km == null`、所有 `distance_m == null`。
- [X] T045 [US3] 依 [quickstart.md](./quickstart.md) V3、V5、V6 手動驗證：高雄座標 → 「附近查無店家」＋可改看全部；`--purge` 後 → 「目前尚無店家資料」且**無**改看按鈕；Location unavailable → 文案與拒絕**明顯不同**且有重試；網路節流至逾時 → 10 秒後進入失敗處理，**不無限期停留在載入狀態**（FR-010）。

**Checkpoint**: 三個 user story 全部可獨立運作，所有降級路徑與空狀態皆有對應畫面

---

## Phase 6: 入口限定（LIFF only）

**Purpose**: 依 brief 排序⑦，核心功能跑通後才處理入口限制。**此階段完成前本輪不算完成**——FR-001〜FR-003 與 SC-006 皆繫於此。

- [X] T046 於 `frontend/src/components/ui/BottomNav.tsx` 將「找餐廳」分頁改為僅在 LIFF 環境顯示，使用既有的 [`isInLiff()`](../../frontend/src/lib/liff/environment.ts)（FR-002、FR-003）。⚠️ **環境判定完成前必須不顯示該分頁**——`isInLiff()` 依賴 `initRuntimeEnv()` 已完成，判定前為 `null` 狀態。寧可晚一瞬間出現，不可在一般網頁短暫閃現（[research.md](./research.md) R-03）。
- [X] T047 於 `frontend/src/app/(app)/restaurants/page.tsx` 與 `[storeId]/page.tsx` 加入非 LIFF 環境的守衛：直接以網址進入時顯示「此功能僅於 LINE 內提供」與返回操作，**不得**白畫面或錯誤畫面（FR-003、憲章原則 II）。
- [X] T048 確認**後端未加任何入口來源檢查**——`GET /stores*` 對所有已登入使用者一視同仁，不存在 LIFF 專屬端點或 `X-Client-Entry` 之類的判斷（憲章原則 III 與架構約束、FR-004）。「僅 LIFF 提供」界定的是哪個入口實作畫面，不是安全邊界；在後端擋來源會構成憲章違規（[research.md](./research.md) R-03）。此為**檢查任務，預期不需修改任何程式碼**。
- [X] T049 [P] 建立 `frontend/tests/e2e/restaurants-entry.spec.ts`：非 LIFF 環境下底部導覽**無**「找餐廳」分頁、直接進入 `/restaurants` 顯示降級說明、且第一輪的儀表板／拍照／趨勢／個人設定**全部正常**（SC-006）。對應 [quickstart.md](./quickstart.md) V9。

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T050 [P] 建立 `backend/tests/integration/test_stores_readonly.py`：以 OpenAPI schema 斷言 `/stores` 相關路徑下**只有 `get` 方法**，且 `POST`／`PATCH`／`DELETE /stores` 皆不存在（FR-029）。這支測試是防止日後「順手」加寫入端點而與第三輪衝突的護欄。對應 [quickstart.md](./quickstart.md) V10。
- [X] T051 [P] 建立 `backend/tests/integration/test_nutrition_isolation.py`：修改 `food_nutrition_references` 中同名食物的數值後，店家餐點頁的數值**完全不變**；反向修改 `menu_items` 亦不影響拍照辨識的換算結果（憲章原則 V、FR-030、FR-031）。並以靜態檢查斷言 `app/services/stores.py` 未 import 第一輪營養模組。對應 [quickstart.md](./quickstart.md) V11。
- [ ] T052 [P] 檢查 `frontend/src/app/(app)/restaurants/` 下所有畫面的深色模式與視覺一致性，色彩、字體、圓角沿用第一輪既有樣式（FR-036）。本輪不對照 prototype——該檔案未涵蓋店家清單與餐點瀏覽畫面。
- [X] T053 [P] 於餐點營養數值附近加入「估算參考值」說明文字，比照第一輪 `capture/page.tsx` 的免責文案（FR-037、FR-038、憲章原則 VII）。
- [X] T054 執行完整測試套件：`cd backend && pytest`、`cd frontend && npm run test`、`npm run typecheck`、`npm run build`、以及兩邊的 lint，全部通過。
- [ ] T055 依 [quickstart.md](./quickstart.md) 逐項執行 V1〜V13（含 V7b）全部驗證情境並記錄結果，特別確認 SC-004 的五類情境（拒絕、定位失敗、附近查無、尚無資料、店家無餐點）各有**可區分**的文案與可執行的下一步。
- [X] T056 確認 SC-007：店家清單與餐點清單在一般網路條件下 2 秒內完成呈現；若未達標，先確認是否為 seed 資料量以外的因素，再考慮 [research.md](./research.md) R-01 記載的 bounding box 粗篩（**本輪不實作**，僅在確有必要時評估）。
- [ ] T057 **【人工，合併前】** 依 [plan.md](./plan.md)「與第三輪分支的合併風險」逐項確認：(1) Alembic 是否雙 head 或版本號撞號；(2) 主鍵型別是否與第三輪一致；(3) 營養欄位 nullability 是否衝突；(4) `store.py` model 檔案是否與對方衝突；(5) `[測試]` 資料是否誤入正式環境；(6) 交接說明中的語意約定（座標選填、名稱不唯一、實刪除＋CASCADE、0 為有效數值）是否已補入共用契約檔案。**不需 agent 自動處理，僅需人工逐項確認並記錄結論。**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**：T001 為**人工阻塞閘**，未完成不得進行 T005；T002 可立即開始
- **Phase 2 Foundational**：依賴 Phase 1；**阻塞所有 user story**
- **Phase 3 US1 (P1)**：依賴 Phase 2 — 本輪 MVP
- **Phase 4 US2 (P2)**：依賴 Phase 2；後端部分可與 Phase 3 平行，前端餐點頁需 T026 的清單頁作為入口
- **Phase 5 US3 (P3)**：依賴 Phase 3（改寫 `restaurants/page.tsx` 的分支）
- **Phase 6 入口限定**：依賴 Phase 3（修改同一批畫面），依 brief 排在最後
- **Phase 7 Polish**：依賴全部前述階段

### Within Phase 2

```
T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010
                                    （T005 需 T001 先完成）
T011 → T012                          （與上列完全獨立，可平行）
```

### Within Phase 3

```
後端：T013 → T014 → T016 → T017 → T018
              └→ T015 [P]
前端：T019 [P] ┐
      T020 [P] ┼→ T026 → T027 → T028
      T021 → T023 ┤
        └→ T022 [P]
      T024 [P] ┤
      T025 [P] ┘
```

後端 T013–T018 與前端 T019–T025 在 T016 完成前可平行推進（前端可先以固定假資料開發畫面），T026 需要真實端點。

### Parallel Opportunities

- **Phase 2**：T011／T012（距離公式）與 T003–T010（資料層）完全獨立，可由兩人同時進行
- **Phase 3**：T015、T018（後端測試）與 T019、T020、T022、T024、T025（前端元件）皆標記 [P]
- **Phase 4**：T031（後端測試）與 T034（前端測試）可平行
- **Phase 7**：T050、T051、T052、T053 四項互不相干，可同時進行

---

## Parallel Example: Phase 3 (US1)

```bash
# 後端測試與前端元件同時開工（T014、T021 完成後）：
Task: "T015 [P] 建立 backend/tests/unit/test_stores_query.py 驗證查詢管線順序"
Task: "T018 [P] 建立 backend/tests/integration/test_stores_api.py 涵蓋附近模式"
Task: "T019 [P] 於 frontend/src/lib/api/types.ts 新增 Store 與 MenuItem 型別"
Task: "T022 [P] 建立 frontend/tests/unit/location.test.ts 驗證錯誤碼映射"
Task: "T024 [P] 建立 frontend/src/lib/format/distance.ts 與其測試"
Task: "T025 [P] 建立 frontend/src/components/restaurants/StoreCard.tsx"
```

---

## Implementation Strategy

### MVP（Phase 1 → 2 → 3）

1. 完成 Phase 1（含 **T001 人工確認閘**）
2. 完成 Phase 2 — 資料表、測試資料、距離公式，全部可用 pytest 驗證
3. 完成 Phase 3 — US1
4. **STOP and VALIDATE**：跑 quickstart V1、V2、V4
5. 此時已可展示核心價值：在 LIFF 內找到附近的店家，且拒絕定位也不會卡住

### Incremental Delivery

1. Phase 2 完成 → 後端距離排序可獨立驗證（不需任何 UI）
2. Phase 3 完成 → **MVP，可展示**
3. Phase 4 完成 → 餐點營養資訊，功能完整
4. Phase 5 完成 → 所有降級路徑與空狀態齊備
5. Phase 6 完成 → 入口限定正確，**本輪功能範圍才算完整**
6. Phase 7 完成 → 可交付

### 兩人分工

- Phase 2：A 做資料層（T003–T010），B 做距離公式（T011–T012）
- Phase 3：A 做後端（T013–T018），B 做前端（T019–T025），於 T026 會合
- Phase 4：A 做後端（T029–T031），B 做前端（T032–T038）
- Phase 5–7：以畫面為單位分工

---

## Notes

- [P] = 不同檔案、無未完成相依，可平行
- 每個任務的描述都標註對應的 FR 或驗收情境，避免只覆蓋 happy path
- **本輪最容易錯且不會報錯的三處**（每一處都有專屬測試）：T014 的管線順序、T033 的 `0` falsy 誤判、T021 的錯誤碼映射
- **兩項人工任務不可由 agent 代勞**：T001（建表前的契約確認）、T057（合併前的檢查清單）
- 每完成一個任務或一組邏輯相關的任務即提交
- 可在任何 Checkpoint 停下來獨立驗證該 story
