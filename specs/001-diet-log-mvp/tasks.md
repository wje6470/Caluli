---

description: "Task list for 拍照飲食紀錄 MVP（第一輪）"
---

# Tasks: 拍照飲食紀錄 MVP（第一輪）

**Input**: Design documents from `/specs/001-diet-log-mvp/`

**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/](./contracts/)、[quickstart.md](./quickstart.md)

**Tests**: 本輪**選擇性納入測試**，但範圍不是任意的——[憲章](../../.specify/memory/constitution.md)「開發流程與品質門檻」明定「涉及登入、權限或營養資料表的變更必須具備對應測試」，並指名兩類必測情境。因此測試任務集中於：憲章必測情境、辨識服務的錯誤分支（本輪技術風險最高處）、以及換算與目標計算公式（數值正確性無法靠人工驗證）。其餘部分不強制 TDD。

**Organization**: 任務依 user story 分組以支援獨立實作與驗收。

## 排序說明（依使用者指定調整）

使用者要求把**資料庫 schema 建置**與 **AI 辨識服務串接**排在前面，UI 打磨排在功能邏輯跑通之後。本清單據此調整：

| 階段 | 內容 | 調整依據 |
|---|---|---|
| Phase 2 | **全部 6 張資料表 + migration**（不只 US1 用得到的表） | 使用者指定；後續所有 UI 任務都讀寫這些表 |
| Phase 3 | **AI 辨識服務串接（後端全段）** | 使用者指定；同時消化 OQ-1 的技術風險（OQ-3 已於 2026-08-04 確認關閉，見下方「契約更新」） |
| Phase 4–8 | 各 user story 的功能邏輯 | 依 spec 優先序 |
| Phase 9 | **UI 打磨與跨切面** | 使用者指定；功能邏輯跑通後才做 |

⚠️ **此排序的代價**：Phase 3 把 US2 的後端段落提前到 US1 之前，因此第一個「可展示的完整使用者流程」（US1 登入建檔）會比嚴格 MVP-first 排法晚約一個階段抵達。換來的是辨識管線的不確定性在投入大量 UI 工作前就被驗證。若你更想要早期可展示成果，把 Phase 3 移到 Phase 4 之後即可，任務內容不需改動——見「Implementation Strategy」。

## ⚠️ 契約更新（2026-08-04）：辨識服務改為真實外部 API

以下 Phase 3 的既有任務（T033〜T048）是依**假定契約**（[contracts/recognition-service.md](./contracts/recognition-service.md) 初版，OQ-3 未確認）完成並通過測試——這段歷史記錄保留不變。

OQ-3 已於 2026-08-04 確認關閉：辨識服務改為第三方代管的「台灣小吃辨識 API」，回應格式與假定契約有實質差異（無 candidates、無 per_100g、無 message，見 [research.md](./research.md) R-16）。既有實作需要一輪遷移才能對接真實服務，任務見新增的「**Phase 3.1：契約遷移**」（T126〜T136），插在 Phase 3 與 Phase 4 之間。

## 實作進度（2026-08-03）

`/speckit.implement` 執行結果：**119/125 完成**。五個 user story 全部可運作，並已對**實際運行中的服務**（依假定契約的 stub）通過 39 項冒煙檢查。Phase 3.1 的契約遷移任務尚未執行，見上方異動說明。

| Phase | 狀態 | 驗證方式 |
|---|---|---|
| 1 Setup | ✅ 完成 | 依賴安裝成功、ruff / eslint 全通過 |
| 2 資料庫 Schema 與核心基礎 | ✅ 完成 | 6 張表建於真 PostgreSQL、24 單元測試 |
| 3 AI 辨識服務串接 | ✅ 完成（T048 除外） | 13 契約 + 11 整合測試 |
| 4 US1 登入與建檔 | ✅ 完成 | 7 登入整合測試、12 環境降級測試 |
| 5 US2 拍照流程 | ✅ 完成 | 10 份量互動測試（含「零 fetch」斷言） |
| 6 US3 儀表板 | ✅ 完成 | 4 儀表板整合測試 |
| 7 US4 趨勢圖表 | ✅ 完成 | 3 趨勢整合測試（含補零與空狀態） |
| 8 US5 資料維護 | ✅ 完成 | 6 維護與隔離整合測試 |
| 9 UI 打磨與跨切面 | ✅ 大致完成 | 見下方剩餘清單 |

### 測試現況（全部實際執行過）

```
backend   uv run pytest              →  72 passed     ruff check    → 全通過
          python tests/smoke_e2e.py  →  39 passed     （對真實服務）
frontend  npm run test               →  22 passed     eslint        → 全通過
          npm run typecheck          →  無錯誤         npm run build → 成功（8 routes）
```

**環境已補齊**：本機原本沒有 Node.js 與 Docker。已安裝 Node v24.18.1（winget user scope）；Docker 因需管理員權限改以 **PostgreSQL 16.4 免安裝二進位檔**（port 55432）取代，`tests/conftest.py` 新增 `TEST_DATABASE_URL` 支援。

### 真實服務冒煙測試（`backend/tests/smoke_e2e.py`）

對實際運行的 API（:8000）、辨識 stub（:8900）與 PostgreSQL 執行 39 項檢查，全數通過。與 pytest 整合測試的差別：那些走 ASGITransport 且在交易中 rollback，這裡是真 HTTP、真資料庫寫入、真辨識服務呼叫，且 **Alembic migration 已在真資料庫上驗證**（先前只驗證過 `create_all`）。

**實測效能（T122）**

| 項目 | 實測 | 門檻 |
|---|---|---|
| 儀表板查詢 | **6 ms** | < 500 ms ✅ |
| 30 天趨勢查詢 | **5 ms** | < 500 ms ✅ |
| 辨識往返（stub） | 319 ms | 供 OQ-4 參考，非真模型 |
| 份量調整重算 | 同步純函式、零 API 呼叫 | < 0.3 s ✅（由 `portion.test.tsx` 斷言） |

### 剩餘 6 項

- **T048 / T125** —— 需真實辨識服務實測延遲以校準 OQ-1／OQ-4。stub 的 319ms 不具代表性；此需求已由新增的 **T139**（Phase 3.1）承接，待契約遷移完成後執行。
- **T120 / T121** —— Playwright 端對端測試。需真 LINE channel 與 HTTPS 通道（LIFF 必需）。冒煙測試已涵蓋後端全路徑，但瀏覽器層的互動未自動化。
- **T123** —— quickstart V1〜V10 的完整人工走查。V3〜V9 的後端路徑已由冒煙測試涵蓋；V1／V2（雙入口登入）需真實 LINE 環境。
- **T119** —— 系統性無障礙稽核。已完成：滑桿 `aria-label`／`aria-valuetext`、Modal 的 `role="dialog"`／Escape 關閉／焦點移入／背景滾動鎖定、載入狀態 `role="status"`。**未完成**：色彩對比的量測與完整鍵盤導覽稽核。

### 實作過程中修正的問題

1. `eslint-config-next` 15.5.x 僅有 `.eslintrc` 進入點，其 `@rushstack/eslint-patch` 與 ESLint 9 flat config 不相容 → 改用 `typescript-eslint` + `react-hooks` 自組規則集，並保留憲章原則 II 的 `no-restricted-imports` 守衛（已建立違規檔案實證可攔截）。
2. 預設 `JWT_SECRET` 僅 18 bytes，低於 HMAC-SHA256 的 32 bytes 建議下限（PyJWT 發出 `InsecureKeyLengthWarning`）→ 已加長並註明正式環境須覆寫。
3. `PortionSlider` 的數值輸入框原本會把空字串立即夾成最小值，導致使用者清空欄位重打時跳成 1、無法正常輸入 → 改為保留輸入中的原始字串，僅在可解析時才送出。
4. `filterwarnings = error` 使整合測試在 skip 之前就 error → 改為就地抑制 testcontainers 的匯入警告。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行執行（不同檔案、無未完成依賴）
- **[Story]**: 對應的 user story（US1–US5）
- 每個任務都標明確切檔案路徑

## Path Conventions

Web app 結構（見 [plan.md](./plan.md) Structure Decision）：`backend/`、`frontend/`、`tools/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 專案初始化與工具鏈

- [X] T001 建立倉庫目錄骨架 `backend/`、`frontend/`、`tools/`，並建立根層 `.gitignore`
- [X] T002 [P] 初始化後端 Python 專案於 `backend/pyproject.toml`（Python 3.12；FastAPI、Pydantic v2、SQLAlchemy 2.0、Alembic、httpx、PyJWT、Pillow、pydantic-settings）
- [X] T003 [P] 初始化前端 Next.js 專案於 `frontend/package.json`（Next.js 15 App Router、React 19、TypeScript strict、`@line/liff`、Tailwind CSS、TanStack Query、Recharts、Zod）
- [X] T004 [P] 設定後端 lint 與格式化（ruff）於 `backend/pyproject.toml`
- [X] T005 [P] 設定前端 lint 與格式化（ESLint + Prettier）於 `frontend/.eslintrc.json`、`frontend/.prettierrc`
- [X] T006 建立 `docker-compose.yml`：PostgreSQL 16 服務 + recognition-stub 服務定義
- [X] T007 [P] 實作後端環境設定於 `backend/app/core/config.py`（Pydantic Settings，變數清單見 [quickstart.md](./quickstart.md)）
- [X] T008 [P] 實作前端環境變數存取與驗證於 `frontend/src/lib/env.ts`（缺少 `NEXT_PUBLIC_LIFF_ID` 時不得崩潰，須降級為 web 模式）

---

## Phase 2: Foundational — 資料庫 Schema 與核心基礎（Blocking Prerequisites）

**Purpose**: 全部資料表、migration 與所有 user story 共用的後端基礎建設

**⚠️ CRITICAL**: 本階段完成前，任何 user story 都無法開始

**⭐ 使用者指定優先**：本階段一次建立 **全部 6 張資料表**，而非只建 US1 需要的兩張——後續儀表板、圖表等任務都依賴完整 schema。

### 資料表與 Migration

- [X] T009 初始化 Alembic 於 `backend/alembic/`，設定 `env.py` 讀取 `DATABASE_URL` 並啟用 `pgcrypto`
- [X] T010 [P] 建立 `users` model 於 `backend/app/db/models/user.py`（含 `role` 欄位，CHECK IN `user`/`admin`，預設 `user`；規格見 [data-model.md](./data-model.md)）
- [X] T011 [P] 建立 `health_profiles` model 於 `backend/app/db/models/health_profile.py`（1:1 UNIQUE user_id、生理範圍 CHECK、BMR/TDEE 與三項目標欄位）
- [X] T012 [P] 建立 `food_nutrition_references` model 於 `backend/app/db/models/food_reference.py`（`model_label` UNIQUE、每 100g 四項營養值、`default_portion_grams`、`name_normalized` 索引）
- [X] T013 [P] 建立 `meal_records` model 於 `backend/app/db/models/meal_record.py`（`record_date` DATE、`(user_id, record_date)` 索引、`recognition_job_id` **不設外鍵**）
- [X] T014 [P] 建立 `meal_items` model 於 `backend/app/db/models/meal_item.py`（**per_100g 四項快照欄位** + 換算後四項結果欄位；`food_reference_id` FK ON DELETE SET NULL）
- [X] T015 [P] 建立 `recognition_jobs` model 於 `backend/app/db/models/recognition_job.py`（`status` CHECK `processing`/`completed`/`failed`、`item_count`、`service_message`、`error_code`、`duration_ms`、`raw_response` JSONB）
- [X] T016 產生並檢閱初始 migration 於 `backend/alembic/versions/`（依賴 T010–T015）
- [X] T017 **憲章原則 V 稽核**：檢查 T016 產出的 migration，確認未建立任何店家／餐點資料表、且 `food_nutrition_references` 無任何指向店家餐點概念的外鍵；將檢查結果註記於 migration 檔頂部註解
- [X] T018 實作 DB session 與 engine 於 `backend/app/db/session.py`
- [X] T019 實作通用食物營養對照表 seed 腳本於 `backend/app/scripts/seed_foods.py`（⚠️ 資料來源見 OQ-2，未定案前先以可替換的 CSV 匯入）

### 共用後端基礎

- [X] T020 [P] 實作錯誤信封與 code→HTTP 對照於 `backend/app/core/errors.py`（`{error: {code, message, retryable}}`，涵蓋 [research.md](./research.md) R-08 表列全部 code）
- [X] T021 [P] 實作 JWT 簽發與解析於 `backend/app/core/security.py`（HS256、`sub` = user UUID、效期取自設定）
- [X] T022 實作依賴注入於 `backend/app/core/deps.py`：`get_current_user()` 與 `require_admin()`（後者本輪**不掛載於任何端點**，僅建立；憲章原則 IV）
- [X] T023 [P] 實作 Asia/Taipei 日期歸屬工具於 `backend/app/core/clock.py`（`captured_at` → `record_date`）
- [X] T024 [P] 實作營養換算與驗算於 `backend/app/services/nutrition.py`（`per_100g × grams / 100`；驗算容忍值 `max(0.5, expected × 0.01)`）
- [X] T025 [P] 實作 BMR/TDEE 與營養素目標計算於 `backend/app/services/targets.py`（Mifflin-St Jeor；係數 1.2/1.45/1.75；公式見 [research.md](./research.md) R-13）
- [X] T026 [P] 實作照片儲存抽象於 `backend/app/services/photo_storage.py`（`{PHOTO_STORAGE_ROOT}/{user_id}/{yyyy}/{mm}/{uuid}.jpg`，介面化以利日後換物件儲存）
- [X] T027 建立 FastAPI app 骨架於 `backend/app/main.py`（CORS、錯誤處理器註冊、`/healthz`、v1 router 掛載）
- [X] T028 [P] 建立型別化 API client 基礎於 `frontend/src/lib/api/client.ts`（Bearer token 附加、401 攔截、錯誤信封解析）
- [X] T029 [P] 由 [contracts/openapi.yaml](./contracts/openapi.yaml) 產生前端型別於 `frontend/src/lib/api/types.ts`

### 憲章必測情境（Foundational）

- [X] T030 [P] 單元測試：`require_admin()` 拒絕一般使用者 token 於 `backend/tests/unit/test_deps.py` ← **憲章明列必測情境**
- [X] T031 [P] 單元測試：營養換算與驗算容忍值於 `backend/tests/unit/test_nutrition.py`
- [X] T032 [P] 單元測試：BMR/TDEE 與三項營養素目標公式於 `backend/tests/unit/test_targets.py`（以手算值比對）

**Checkpoint**: 完整 schema 與後端基礎就緒——所有 user story 皆可開始

---

## Phase 3: AI 辨識服務串接（後端全段）

**⭐ 使用者指定優先**：本階段整段屬 US2，但提前於 US1 之前執行。除使用者指示外，另有技術理由——同步／非同步與回應時間亦未定（OQ-1），提前驗證可在投入 UI 工作前暴露落差。

> 本階段的任務原依假定契約（OQ-3 未確認）撰寫並實作完成；OQ-3 已於 2026-08-04 確認關閉，實際契約與假定有實質差異，遷移任務見下方「Phase 3.1」，不在此重寫既有任務內容。

**Goal**: 後端可接收照片、呼叫辨識服務、查表換算、並正確區分「未偵測到食物」與各類錯誤

**Independent Test**: 不需前端——以 `curl` 上傳照片至 `POST /api/v1/recognitions`，切換 stub 六種模式，驗證回應的 `status`、`items`、HTTP 狀態碼與 `recognition_jobs` 資料列皆符合 [contracts/recognition-service.md](./contracts/recognition-service.md) 的情境對照表

- [X] T033 [US2] 實作可切換模式的辨識 stub 服務於 `tools/recognition-stub/stub.py`（模式：`normal`／`empty`／`timeout`／`error`／`garbage`／`unknown_label`，定義見 [contracts/recognition-service.md](./contracts/recognition-service.md)）
- [X] T034 [US2] 實作辨識服務 adapter 於 `backend/app/services/recognition_client.py` ← ★ **OQ-3 的唯一接觸點**，契約若有出入只改此檔
- [X] T035 [US2] 於 T034 中實作逾時控制（`RECOGNITION_TIMEOUT_SECONDS`，預設 30）與**不自動重試**策略（[research.md](./research.md) R-08）
- [X] T036 [P] [US2] 定義辨識相關 Pydantic schemas 於 `backend/app/schemas/recognition.py`（`Recognition`、`RecognitionItem`、`Per100g`、`FoodCandidate`；欄位須與 [contracts/openapi.yaml](./contracts/openapi.yaml) 完全一致）
- [X] T037 [US2] 實作「模型 label → 營養對照表查表 → 組成 `per_100g` 與 `default_portion_grams`」轉換於 `backend/app/services/recognition_client.py` ← ★ **`per_100g` 必須進入回應**，否則前端無法即時換算（FR-031〜034）
- [X] T038 [US2] 於 T037 中處理查表失敗：該品項 `nutrition_available: false`、仍列出名稱（FR-037）
- [X] T039 [US2] 於 T037 中處理 Top-K 候選：逐一查表組成 `candidates` 陣列供使用者改選（FR-035）
- [X] T040 [US2] 實作 `POST /api/v1/recognitions` 於 `backend/app/api/v1/recognitions.py`（multipart 接收、格式與大小驗證 → 415/413、存檔、建立 `recognition_jobs`、同步呼叫、回寫結果）
- [X] T041 [US2] 於 T040 中實作 **`items: []` 走成功路徑**：`status='completed'`、`item_count=0`、原樣保留 `service_message`、HTTP 200 ← ★ **不得歸為錯誤**（FR-027）
- [X] T042 [US2] 於 T040 中實作錯誤分支映射：逾時→504 `RECOGNITION_TIMEOUT`、5xx／連線失敗→503 `RECOGNITION_UNAVAILABLE`、無法解析→502 `RECOGNITION_BAD_RESPONSE`，並回寫 `recognition_jobs.error_code`
- [X] T043 [US2] 實作 `GET /api/v1/recognitions/{id}` 於 `backend/app/api/v1/recognitions.py`（擁有者驗證，非本人一律 404）
- [X] T044 [US2] 實作 `POST /api/v1/recognitions/{id}/retry` 於 `backend/app/api/v1/recognitions.py`（**重用既有照片，不需重新上傳**；`retry_count` 遞增）（FR-028）
- [X] T045 [P] [US2] 實作 `GET /api/v1/foods/search` 於 `backend/app/api/v1/foods.py`（供手動修正名稱使用；僅查通用食物表）
- [X] T046 [P] [US2] 契約測試：對 stub 六種模式各驗證一次於 `backend/tests/contract/test_recognition_service.py`
- [X] T047 [P] [US2] 整合測試：辨識端點的成功／空結果／三類錯誤／重試路徑於 `backend/tests/integration/test_recognitions.py`
- [ ] T048 [US2] 以 `recognition_jobs.duration_ms` 收集實測延遲並記錄於 [plan.md](./plan.md) OQ-1／OQ-4，判定是否需改為非同步（[research.md](./research.md) R-07 遷移評估）

**Checkpoint**: 辨識管線後端完整可用且錯誤分支全數驗證——前端可安心接手

---

## Phase 3.1: 契約遷移——串接真實外部辨識 API（2026-08-04 新增）

**Goal**: 把 Phase 3 已完成、依假定契約運作的辨識管線，改為對接已確認的真實外部服務（「台灣小吃辨識 API」），契約差異依 [research.md](./research.md) R-16 的決策全數收斂在 `recognition_client.py`

**Independent Test**: 以 `curl` 直接呼叫真實服務驗證回應格式；再以更新後的 stub 走一次 [quickstart.md](./quickstart.md) V3〜V5，確認前端與對外契約（`openapi.yaml`）**不需任何改動**即可運作；`GET /api/v1/foods/search` 承接原候選改選的修正入口

**前置**：[contracts/recognition-service.md](./contracts/recognition-service.md)（2026-08-04 修訂版）、research.md R-16

- [X] T126 [US2] 於 `backend/app/core/config.py` 新增 `recognition_api_key` 設定項（對應 `RECOGNITION_API_KEY`）；`recognition_service_url` 正式環境改指向 `https://taiwanese-food-api-528488788338.asia-east1.run.app`，本機／CI 維持指向 stub
- [X] T127 [US2] 改寫 `backend/app/services/recognition_client.py` 的 `call_recognition_service()`：URL 拼接改為 `{base}/api/detect`、multipart 欄位名由 `photo` 改為 `file`、加入 `X-API-Key` header（值取自 T126）；`401` 回應映射為 `RECOGNITION_UNAVAILABLE`（不對外揭露認證細節）
- [X] T128 [US2] 改寫 `backend/app/services/recognition_client.py` 的 `build_items()`：改解析新回應格式（`name`／`estimated_weight_g`／`calories`／`protein_g`／`carbs_g`／`fat_g`／`confidence`／`class_name`／`bbox`），以 `value / estimated_weight_g × 100` 反推 `per_100g` ← ★ **對前端與 `openapi.yaml` 的 `per_100g` 契約必須透明，前端不應因此變動**（R-16 決策 1）
- [X] T129 [US2] 於 T128 中將 `bbox` 座標由 `{x1,y1,x2,y2}` 轉換為既有 schema 的 `{x,y,width,height}`（`x=x1, y=y1, width=x2-x1, height=y2-y1`）
- [X] T130 [US2] 於 T128 中移除「查 `food_nutrition_references` 換算」邏輯：`food_reference_id` 一律 `null`、`nutrition_available` 除下方防禦性情況外一律 `true`、`candidates` 一律回傳空陣列 `[]`（R-16 決策 2）
- [X] T131 [US2] 於 T128 中加入防禦性檢查：`estimated_weight_g` 為 0／缺漏／非正數時，該品項 `per_100g = null`、`nutrition_available = false`，仍列出 `name`，不得讓整次辨識失敗
- [X] T132 [US2] 於 `recognition_client.py` 加入 `items: []` 時的固定中文文案合成（例如「沒有偵測到食物，請換一張再試試」），寫入 `recognition_jobs.service_message`——上游不再提供 `message` 欄位
- [X] T133 [P] [US2] 檢視 `backend/app/schemas/recognition.py`：確認 `Per100g`／`RecognitionItem`／`FoodCandidate` 因 R-16 決策 1、2 維持不變即可滿足新契約；若確認不需改動，僅更新相關 docstring 說明來源已改為反推值
- [X] T134 [US2] 改寫 `tools/recognition-stub/stub.py`：回應格式對齊真實契約（`estimated_weight_g`＋絕對值＋`bbox:{x1,y1,x2,y2}`，無 `candidates`／`message`）；模式清單改為 `normal`／`empty`／`timeout`／`error`／`unauthorized`／`garbage`／`zero_weight`（移除 `unknown_label`，新增 `unauthorized` 與 `zero_weight`）
- [X] T135 [P] [US2] 更新 `backend/tests/contract/test_recognition_service.py`：fixture 改用新回應格式；新增 `zero_weight`（驗證 T131 防禦邏輯）與 `unauthorized`（驗證 401 → `RECOGNITION_UNAVAILABLE`）兩組契約測試
- [X] T136 [P] [US2] 更新 `backend/tests/integration/test_recognitions.py` 與 `backend/tests/smoke_e2e.py` 對辨識回應內容的既有斷言，改為驗證新格式下 `per_100g` 反推值正確、`candidates` 恆空、`food_reference_id` 恆 `null`
- [X] T137 [US2] 檢視 `frontend/src/components/capture/RecognitionItemCard.tsx`（T080 原「候選名稱改選」邏輯）：`candidates` 恆為空陣列時是否已優雅降級（隱藏候選 UI、引導改用既有的 `GET /foods/search` 手動搜尋入口，即 T082）；若元件目前假設 `candidates` 必有值，需調整為以陣列長度判斷是否顯示候選區塊 ← **驗證結果：`hasCandidates = item.candidates.length > 1` 已用長度判斷，無需改動**
- [X] T138 [P] 同步更新 `backend/.env.example`：新增 `RECOGNITION_API_KEY`，`RECOGNITION_SERVICE_URL` 註解註明正式環境的真實 base URL（[quickstart.md](./quickstart.md) 已於 plan 階段更新，此處確保範例檔一致）
- [ ] T139 [US2] 以真實外部 API（而非 stub）實際跑一次 `POST /api/v1/recognitions` 端到端請求，記錄 `recognition_jobs.duration_ms` 作為 OQ-1／OQ-4 的**首次真實數據**（取代原 T048 的 stub 延遲 319ms，該數據依 contracts/recognition-service.md 註記為不具代表性）← **阻塞中：需要真實 `RECOGNITION_API_KEY` 才能執行，本機沒有金鑰**

**Checkpoint**: 辨識管線改為真實外部 API 且既有前端／對外契約零改動；Phase 5（US2 前端）與既有測試套件可在此基礎上直接複用

---

## Phase 4: User Story 1 - 從 LINE 入口登入並取得每日熱量目標 (Priority: P1) 🎯 MVP

**Goal**: 使用者可從 LIFF 或一般瀏覽器完成 LINE 登入，首次使用者填寫個人資訊後取得每日熱量與營養素目標

**Independent Test**: 兩種入口各走一次「進入 → 登入 → 填寫個人資訊 → 看到每日建議熱量」；同一 LINE 帳號在兩入口看到同一份資料（[quickstart.md](./quickstart.md) V1、V2）

### 後端

- [X] T049 [US1] 實作**單一 LINE 驗證核心** `verify_line_identity()` 於 `backend/app/services/line_auth.py` ← ★ **憲章原則 I**：回傳的 `LineIdentity` **不得**含任何來源入口欄位
- [X] T050 [US1] 於 `backend/app/services/line_auth.py` 實作 ID Token 驗證（LIFF 入口用）
- [X] T051 [US1] 於 `backend/app/services/line_auth.py` 實作 authorization code → ID Token 交換（網頁 OAuth 入口用），完成後**交給同一個 T049 核心**
- [X] T052 [US1] 實作 `POST /api/v1/auth/line/liff` 於 `backend/app/api/v1/auth.py`
- [X] T053 [US1] 實作 `POST /api/v1/auth/line/callback` 於 `backend/app/api/v1/auth.py`
- [X] T054 [US1] 實作使用者建立／查詢與 session 簽發於 `backend/app/services/line_auth.py`（兩入口共用，`line_user_id` 為唯一鍵）
- [X] T055 [P] [US1] 實作 `GET /api/v1/me` 於 `backend/app/api/v1/profile.py`（回傳 `profile_completed` 供前端決定是否導向 onboarding）
- [X] T056 [US1] 實作 `PUT /api/v1/me/profile` 於 `backend/app/api/v1/profile.py`（驗證生理範圍 → 422；呼叫 T025 計算目標；**忽略客戶端傳入的 BMR/TDEE 欄位**）
- [X] T057 [P] [US1] 定義 profile 相關 schemas 於 `backend/app/schemas/profile.py`

### 前端

- [X] T058 [US1] 實作**環境判斷與能力包裝模組**於 `frontend/src/lib/liff/environment.ts` ← ★ **憲章原則 II**：`liff.init()` 失敗一律降級為 `web`（正常路徑，不拋錯）；對外只暴露 `getRuntimeEnv()` 與包裝後的能力函式，**不外洩原始 `liff` 物件**
- [X] T059 [US1] 實作環境 Context 於 `frontend/src/app/layout.tsx`（全應用只判斷一次並快取）
- [X] T060 [US1] 實作登入頁於 `frontend/src/app/login/page.tsx`（LIFF 環境自動登入；web 環境顯示「使用 LINE 登入」按鈕）
- [X] T061 [US1] 實作 OAuth 回呼頁於 `frontend/src/app/auth/callback/page.tsx`（含使用者取消授權的處理，不得出現空白或錯誤畫面）
- [X] T062 [US1] 實作登入守衛與原目標路徑記憶於 `frontend/src/app/(app)/layout.tsx`（401 → 導回登入 → 完成後回原頁）（FR-008）
- [X] T063 [US1] 實作多步驟建檔流程於 `frontend/src/app/onboarding/page.tsx`（性別／年齡／身高／體重／活動量，步驟指示器與進度條）
- [X] T064 [US1] 實作 TDEE 結果頁於 `frontend/src/app/onboarding/page.tsx`（顯示每日建議熱量與三項營養素目標）
- [X] T065 [US1] 實作未建檔導向邏輯（`profile_completed === false` 時不允許進入 `/dashboard`，含直接輸入網址的情況）（FR-013）

### 憲章必測情境（US1）

- [X] T066 [P] [US1] 單元測試：`liff.init()` 失敗時 `getRuntimeEnv()` 回傳 `web` 且不拋錯於 `frontend/tests/unit/environment.test.ts` ← **憲章明列必測情境**
- [X] T067 [P] [US1] 整合測試：兩支登入端點皆收斂至同一驗證核心、同一 `line_user_id` 對應同一 user 於 `backend/tests/integration/test_auth.py`

**Checkpoint**: US1 完整可用——已是可展示的最小產品

---

## Phase 5: User Story 2 - 拍照辨識、調整份量並儲存紀錄 (Priority: P2)

**Goal**: 使用者可上傳照片、看到辨識結果、即時調整份量、確認後儲存並返回儀表板

**Independent Test**: 以一張照片走完「上傳 → Loading → 結果 → 調整份量看到數值即時變動 → 儲存」（[quickstart.md](./quickstart.md) V3〜V5）

> 後端辨識管線已於 Phase 3 完成，本階段聚焦前端流程與紀錄儲存。

### 後端（紀錄儲存）

- [X] T068 [P] [US2] 定義紀錄相關 schemas 於 `backend/app/schemas/meal_record.py`（`MealRecordInput`、`MealItemInput`、`MealRecord`）
- [X] T069 [US2] 實作 `POST /api/v1/meal-records` 於 `backend/app/api/v1/meal_records.py`（**後端以 T024 重新驗算每個品項**，差異超過容忍值以後端值為準；`record_date` 由 T023 換算）
- [X] T070 [P] [US2] 實作 `GET /api/v1/meal-records` 於 `backend/app/api/v1/meal_records.py`
- [X] T071 [P] [US2] 實作 `GET /api/v1/meal-records/{id}/photo` 於 `backend/app/api/v1/meal_records.py`（驗證擁有者後回傳，**不開放靜態目錄**）

### 前端（拍照與確認流程）

- [X] T072 [P] [US2] 實作前端換算工具於 `frontend/src/lib/nutrition.ts`（與後端 T024 同一公式；熱量取整、營養素一位小數）
- [X] T073 [US2] 實作 `useRecognition()` hook 於 `frontend/src/hooks/useRecognition.ts` ← ★ **以 `status` 驅動的狀態機，須預留 `processing` 分支**（本輪不會觸發，但非同步遷移時不需改畫面；[research.md](./research.md) R-07）
- [X] T074 [US2] 實作拍照／相簿選取與前端壓縮於 `frontend/src/app/(app)/capture/page.tsx`（最長邊 1280px、JPEG 0.85；相機權限被拒時降級為相簿上傳）（FR-018）
- [X] T075 [US2] 實作送出前的格式與大小驗證於 `frontend/src/app/(app)/capture/page.tsx`（FR-019）
- [X] T076 [P] [US2] 實作 Loading 狀態元件於 `frontend/src/components/capture/LoadingState.tsx`（辨識期間全程顯示；送出按鈕須防重複點擊）（FR-025、FR-026）
- [X] T077 [US2] 實作 `PortionSlider` 元件於 `frontend/src/components/capture/PortionSlider.tsx` ← ★ **預設值 + 可即時互動調整**，上下限約束（FR-031、FR-034）
- [X] T078 [US2] 實作 `RecognitionItemCard` 元件於 `frontend/src/components/capture/RecognitionItemCard.tsx`（名稱、份量、熱量、三大營養素；**份量變動即時重算，調整期間不得發出任何 API 請求**）（FR-032、SC-003）
- [X] T079 [US2] 實作合計即時連動於 `frontend/src/app/(app)/capture/page.tsx`（任一品項變動 → 合計同步更新）（FR-033）
- [X] T080 [US2] 實作候選名稱改選於 `frontend/src/components/capture/RecognitionItemCard.tsx`（改選後以新食物的 `per_100g` 與 `default_portion_grams` 重新換算）（FR-035）
- [X] T081 [US2] 實作品項移除於 `frontend/src/components/capture/RecognitionItemCard.tsx`（移除後不列入合計、不被儲存）（FR-036）
- [X] T082 [US2] 實作手動修正名稱與數值於 `frontend/src/components/capture/RecognitionItemCard.tsx`（串接 `GET /foods/search`；`nutrition_available: false` 時標示無法自動換算）（FR-037）
- [X] T083 [US2] 實作餐別選擇於 `frontend/src/app/(app)/capture/page.tsx`（依當下時間給預設值）（FR-038）
- [X] T084 [US2] 實作 `EmptyResultGuide` 元件於 `frontend/src/components/capture/EmptyResultGuide.tsx` ← ★ **`items: []` 的專屬引導畫面**：顯示服務回傳訊息 +「重新拍攝」「返回」，**不得渲染空清單或落入通用錯誤畫面**（FR-027）
- [X] T085 [US2] 實作 `ErrorState` 元件於 `frontend/src/components/capture/ErrorState.tsx`（逾時／服務不可用／回應異常各有說明；依 `retryable` 決定是否顯示「重試」；連續 3 次失敗後另外顯示「返回」）（FR-028、FR-029）
- [X] T086 [US2] 串接重試流程於 `frontend/src/hooks/useRecognition.ts`（呼叫 `POST /recognitions/{id}/retry`，**不重新選取照片**）
- [X] T087 [US2] 實作儲存與返回於 `frontend/src/app/(app)/capture/page.tsx`（儲存後 invalidate 儀表板 query，返回時數值已更新，**無需手動重新整理**）（FR-041）
- [X] T088 [US2] 實作放棄流程（取消／離開不建立任何紀錄）（FR-030、US2 情境 9）
- [X] T089 [P] [US2] 單元測試：份量調整重算正確且**不觸發 API 呼叫**於 `frontend/tests/unit/portion.test.tsx`

**Checkpoint**: US1 + US2 皆可獨立運作——核心價值主張已完整交付

---

## Phase 6: User Story 3 - 每日熱量目標追蹤儀表板 (Priority: P3)

**Goal**: 使用者可看到當日建議／已攝取／剩餘熱量、三大營養素進度與當日紀錄清單，並可切換日期與檢視視角

**Independent Test**: 在已有目標值與若干筆紀錄的帳號上開啟儀表板，驗證「建議 − 已攝取 = 剩餘」、切換日期與視角（[quickstart.md](./quickstart.md) V6）

- [X] T090 [US3] 實作儀表板聚合服務於 `backend/app/services/analytics.py`（單日彙總，含 `over_target` 判定）
- [X] T091 [US3] 實作 `GET /api/v1/dashboard` 於 `backend/app/api/v1/analytics.py`（`date` 未帶時取 Asia/Taipei 今日）
- [X] T092 [P] [US3] 實作熱量主卡元件於 `frontend/src/components/dashboard/CalorieHeroCard.tsx`（環形進度 + 進度條；超標時明確標示）（FR-048）
- [X] T093 [P] [US3] 實作三大營養素卡片於 `frontend/src/components/dashboard/MacroCards.tsx`
- [X] T094 [P] [US3] 實作「已攝取／尚缺」視角切換於 `frontend/src/components/dashboard/ViewModeToggle.tsx`（FR-047）
- [X] T095 [P] [US3] 實作日期切換條於 `frontend/src/components/dashboard/DateStrip.tsx`（FR-050）
- [X] T096 [US3] 實作當日紀錄清單於 `frontend/src/components/dashboard/MealList.tsx`（含照片縮圖、無紀錄時的空狀態）（FR-049）
- [X] T097 [US3] 組裝儀表板頁於 `frontend/src/app/(app)/dashboard/page.tsx`

**Checkpoint**: 使用者每天回訪的落點已就緒

---

## Phase 7: User Story 4 - 檢視飲食趨勢圖表 (Priority: P4)

**Goal**: 使用者可檢視近 7／14／30 天的攝取趨勢，切換四種指標並看到摘要數值

**Independent Test**: 在有多日紀錄（含空白日）的帳號上切換區間與指標，驗證數值與各日紀錄一致、空白日顯示 0（[quickstart.md](./quickstart.md) V7）

- [X] T098 [US4] 實作趨勢聚合服務於 `backend/app/services/analytics.py`（依 `record_date` 分組；**後端補齊完整日期序列，無紀錄日填 0**）（FR-054）
- [X] T099 [US4] 實作 `GET /api/v1/trends` 於 `backend/app/api/v1/analytics.py`（含 `average` 與 `target_achievement_rate`）
- [X] T100 [P] [US4] 實作趨勢圖表元件於 `frontend/src/components/trends/TrendChart.tsx`（Recharts；含無資料空狀態）
- [X] T101 [P] [US4] 實作區間與指標切換於 `frontend/src/components/trends/TrendControls.tsx`
- [X] T102 [P] [US4] 實作摘要卡片於 `frontend/src/components/trends/TrendSummary.tsx`（平均每日攝取、目標達成率）
- [X] T103 [US4] 組裝趨勢頁於 `frontend/src/app/(app)/trends/page.tsx`（無任何紀錄時顯示引導建立第一筆的空狀態）（FR-055）

**Checkpoint**: 累積型價值已就緒

---

## Phase 8: User Story 5 - 維護個人資訊與既有紀錄 (Priority: P5)

**Goal**: 使用者可修改個人資訊並重算目標，可編輯或刪除既有飲食紀錄

**Independent Test**: 改體重後確認目標值變動但歷史紀錄不變；編輯與刪除紀錄後確認該日合計與趨勢同步（[quickstart.md](./quickstart.md) V8）

- [X] T104 [P] [US5] 實作 `PATCH /api/v1/meal-records/{id}` 於 `backend/app/api/v1/meal_records.py`（重新驗算；擁有者驗證失敗回 404）
- [X] T105 [P] [US5] 實作 `DELETE /api/v1/meal-records/{id}` 於 `backend/app/api/v1/meal_records.py`（連同照片檔案刪除，見 OQ-5）
- [X] T106 [US5] 實作個人設定頁於 `frontend/src/app/(app)/profile/page.tsx`（顯示現有數據與目標；可修改並重算）
- [X] T107 [US5] 實作紀錄編輯介面於 `frontend/src/components/dashboard/MealEditSheet.tsx`（份量、名稱、營養值；儲存後該日合計同步更新）
- [X] T108 [US5] 實作紀錄刪除與確認於 `frontend/src/components/dashboard/MealList.tsx`
- [X] T109 [P] [US5] 整合測試：目標重算**不影響**既有 `meal_items` 數值於 `backend/tests/integration/test_profile_recalc.py`（FR-016、快照機制 [research.md](./research.md) R-11）

### 憲章必測情境（資料隔離）

- [X] T110 [P] [US5] 整合測試：以他人 token 存取紀錄、照片、編輯、刪除皆回 404 於 `backend/tests/integration/test_data_isolation.py`（FR-044、SC-009）

**Checkpoint**: 全部五個 user story 皆可獨立運作，功能邏輯完整

---

## Phase 9: UI 打磨與跨切面

**⭐ 使用者指定順序**：本階段安排在所有功能邏輯跑通之後。

**Purpose**: 視覺對齊、跨故事一致性、驗收與文件

### 視覺與互動（對照 prototype）

- [X] T111 [P] 抽取 prototype 視覺語彙為 Tailwind theme 於 `frontend/tailwind.config.ts`（品牌色階、圓角尺度、陰影階層、字重；**參考 [prototype](../../reference/prototype/caiuli.html) 的色彩與樣式，不照抄其結構**）
- [X] T112 實作深色模式切換與**無閃爍初始化**於 `frontend/src/app/layout.tsx`（載入前 inline script 套用 `dark` class）
- [X] T113 [P] 實作底部導覽列與分頁切換節奏於 `frontend/src/components/ui/BottomNav.tsx`
- [X] T114 [P] 實作 Modal 開合動畫於 `frontend/src/components/ui/Modal.tsx`（拍照、辨識確認、編輯等全屏流程共用）
- [X] T115 [P] 統一空狀態與載入骨架元件於 `frontend/src/components/ui/EmptyState.tsx`、`frontend/src/components/ui/Skeleton.tsx`
- [X] T116 [P] 統一數值排版（等寬數字，避免更新時跳動）於 `frontend/src/styles/globals.css`

### 憲章與合規

- [X] T117 加入估算值說明與免責文案於辨識結果畫面與儀表板 ← **憲章原則 VII**（FR-057、FR-058）
- [X] T118 全站文案稽核：確認無疾病判讀、過敏建議、處方或醫療效力暗示（[quickstart.md](./quickstart.md) V10）

### 品質與驗收

- [ ] T119 [P] 無障礙檢查：份量滑桿的鍵盤操作與 aria 標註、色彩對比於 `frontend/src/components/capture/PortionSlider.tsx` 等關鍵元件
- [ ] T120 [P] 端對端測試：LIFF 入口完整流程於 `frontend/tests/e2e/liff-flow.spec.ts`
- [ ] T121 [P] 端對端測試：一般瀏覽器入口完整流程於 `frontend/tests/e2e/web-flow.spec.ts` ← **憲章明列必測情境**
- [X] T122 效能驗證：儀表板與 30 天趨勢查詢 < 500 ms；份量調整重算 < 0.3 秒（SC-003）
- [ ] T123 執行 [quickstart.md](./quickstart.md) 全部 10 組驗證情境（V1〜V10）並記錄結果
- [X] T124 [P] 撰寫專案 README 與部署說明於 `README.md`
- [ ] T125 依 T048 的實測結果回填 OQ-1／OQ-4 結論至 [plan.md](./plan.md)，並判定是否需啟動非同步遷移

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**：無依賴，可立即開始
- **Phase 2 Foundational**：依賴 Phase 1 — **阻塞所有後續階段**
- **Phase 3 辨識串接**：依賴 Phase 2（需要 `food_nutrition_references`、`recognition_jobs`、錯誤信封、照片儲存）
- **Phase 3.1 契約遷移**：依賴 Phase 3（改寫其產出的 `recognition_client.py`／stub／測試），**不依賴** Phase 4；可視為 Phase 3 的延伸，插在 Phase 3 與 Phase 4 之間執行，或與 Phase 4 平行
- **Phase 4 US1**：依賴 Phase 2；**不依賴 Phase 3／3.1**（可與 Phase 3／3.1 平行）
- **Phase 5 US2**：依賴 Phase 3（辨識後端）＋ Phase 3.1（真實契約，前端才會消費到真實資料而非 stub 假定格式）+ Phase 4（登入）
- **Phase 6 US3**：依賴 Phase 2 + Phase 4；有 US2 的紀錄資料時展示效果較完整
- **Phase 7 US4**：依賴 Phase 2 + Phase 4
- **Phase 8 US5**：依賴 Phase 5（紀錄需先能建立）+ Phase 6（編輯入口在紀錄清單上）
- **Phase 9 打磨**：依賴所有欲交付的 user story 完成

### User Story Dependencies

- **US1（P1）**：Phase 2 完成後即可開始 — 無其他故事依賴
- **US2（P2）**：後端段落（Phase 3）Phase 2 後即可開始；前端段落需 US1 的登入
- **US3（P3）**：需 US1（目標值）；紀錄為空時仍可獨立驗收（顯示空狀態）
- **US4（P4）**：需 US1；無紀錄時顯示空狀態，可獨立驗收
- **US5（P5）**：需 US2（有紀錄可編輯）與 US3（編輯入口）

### Parallel Opportunities

| 階段 | 可平行的任務 |
|---|---|
| Phase 1 | T002–T005、T007–T008 |
| Phase 2 | **T010–T015（6 張 model 可同時寫）**；T020–T021、T023–T026、T028–T029；T030–T032 |
| Phase 3 | T036、T045、T046–T047 |
| Phase 3.1 | T133、T135–T136、T138 |
| Phase 4 | T055、T057；T066–T067；**後端（T049–T057）與前端（T058–T065）可由兩人分工** |
| Phase 5 | T068、T070–T072、T076、T089 |
| Phase 6 | **T092–T095（四個獨立元件）** |
| Phase 7 | T100–T102 |
| Phase 8 | T104–T105、T109–T110 |
| Phase 9 | T111、T113–T116、T119–T121、T124 |

**跨階段平行**：Phase 3（辨識後端）與 Phase 4（US1）互不依賴，兩人團隊可同時進行——這也讓「辨識前置」不至於延後 MVP 抵達時間。

---

## Parallel Example: Phase 2 資料表

```bash
# 6 張 model 彼此獨立，可同時開工：
Task: "建立 users model 於 backend/app/db/models/user.py"
Task: "建立 health_profiles model 於 backend/app/db/models/health_profile.py"
Task: "建立 food_nutrition_references model 於 backend/app/db/models/food_reference.py"
Task: "建立 meal_records model 於 backend/app/db/models/meal_record.py"
Task: "建立 meal_items model 於 backend/app/db/models/meal_item.py"
Task: "建立 recognition_jobs model 於 backend/app/db/models/recognition_job.py"

# 全部完成後才產生 migration（T016）
```

## Parallel Example: Phase 6 儀表板元件

```bash
Task: "實作熱量主卡於 frontend/src/components/dashboard/CalorieHeroCard.tsx"
Task: "實作三大營養素卡片於 frontend/src/components/dashboard/MacroCards.tsx"
Task: "實作視角切換於 frontend/src/components/dashboard/ViewModeToggle.tsx"
Task: "實作日期切換條於 frontend/src/components/dashboard/DateStrip.tsx"
```

---

## Implementation Strategy

### 依使用者指定順序（本清單預設）

1. Phase 1 Setup
2. Phase 2 **全部資料表 + 核心基礎**
3. Phase 3 **AI 辨識服務串接（後端）** ← 技術風險前置
4. Phase 4 US1 → **停下驗收**（第一個可展示的完整流程）
5. Phase 5 US2 → 驗收 → 核心價值完整
6. Phase 6–8 US3 → US4 → US5，每個階段後驗收
7. Phase 9 UI 打磨與跨切面

### 若改採嚴格 MVP-First

把 **Phase 3（+3.1）移到 Phase 4 之後**即可，任務內容完全不需修改：Phase 1 → 2 → 4（US1，可展示）→ 3 → 3.1 → 5 → …。代價是辨識管線的不確定性（OQ-1，回應時間 p95）要到較晚才會暴露。

**建議折衷**：兩人以上團隊直接讓 Phase 3 與 Phase 4 平行——兩者互不依賴，既前置了風險，也不延後 MVP。

### 增量交付檢查點

| 完成到 | 可展示的成果 |
|---|---|
| Phase 4 | 使用者能登入並看到自己的每日熱量目標 |
| Phase 5 | 拍照記帳完整可用（**核心價值主張**） |
| Phase 6 | 每日追蹤閉環完成 |
| Phase 7 | 長期趨勢，留存價值 |
| Phase 8 | 資料可維護，長期使用不失真 |
| Phase 9 | 可對外發布的品質 |

---

## Notes

- `[P]` = 不同檔案、無未完成依賴，可平行
- `[Story]` 標籤對應 spec.md 的 user story，供追溯
- ★ 標記的任務承載不可妥協的需求或憲章原則，偏離會導致返工——實作前請先讀對應的 research.md 章節
- Phase 3／3.1 的任務雖標 `[US2]`，但刻意提前執行（使用者指定 + 技術風險前置）
- 每個任務或邏輯群組完成後即 commit
- 任一 Checkpoint 皆可停下獨立驗收
- 阻塞中的 open questions（OQ-1、OQ-2、OQ-7、OQ-9）需在對應任務開始前確認：OQ-2／OQ-7 影響 T011／T012／T019，OQ-1 影響 T139／T125，OQ-9（金鑰輪替流程）影響 T126 的正式環境部署
- **OQ-3 已於 2026-08-04 確認關閉**（見 [contracts/recognition-service.md](./contracts/recognition-service.md)、research.md R-16），原本因 OQ-3 而標為「假定」的 T034／T037／T039 等任務內容已由 Phase 3.1（T126〜T139）承接遷移；Phase 3 的原始任務記錄保留不變，作為「依假定契約完成」的歷史紀錄
