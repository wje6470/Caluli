# Implementation Plan: 拍照飲食紀錄 MVP（第一輪）

**Branch**: `001-diet-log-mvp` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-diet-log-mvp/spec.md`；技術規劃補充依據 [reference/round1-plan-brief.md](../../reference/round1-plan-brief.md)

## Summary

本輪交付一套以 LINE 身分登入的拍照飲食紀錄服務：使用者從 LINE 官方帳號或一般瀏覽器進入，完成 LINE 登入與個人健康檔案建檔後取得每日熱量目標，拍照或上傳相簿照片交由第三方代管的「台灣小吃辨識 API」判別食物並直接取得估計份量與熱量／三大營養素，後端套用初始估計份量換算供使用者**即時調整**後儲存，並以儀表板與趨勢圖表呈現攝取狀況。

技術取徑：Next.js 前端同時支援 LIFF 與一般瀏覽器（環境判斷收斂為單一模組，能力經包裝存取）；FastAPI 後端以單一驗證核心處理兩種入口的 LINE 憑證；PostgreSQL 儲存使用者、飲食紀錄與**獨立的**通用食物營養對照表（現僅供手動搜尋修正名稱使用，見 R-16）。辨識服務以同步 HTTP 呼叫串接外部雲端 API（`X-API-Key` 認證），但對前端暴露的 API 仍採資源導向形狀（`{id, status, items}`）並預先實作 `processing` 狀態機，使未來改為非同步時不需破壞契約——這是本輪最重要的架構隔離決策。份量換算完全在前端執行；後端 adapter 由外部服務的絕對值反推 `per_100g` 供前端消費，並於儲存時重新驗算。

## Technical Context

**Language/Version**: TypeScript 5.x / Node.js 20 LTS（前端）；Python 3.12（後端）

**Primary Dependencies**:

- 前端 — Next.js 15（App Router）、React 19、`@line/liff`、Tailwind CSS、TanStack Query、Recharts、Zod
- 後端 — FastAPI、Pydantic v2、SQLAlchemy 2.0、Alembic、httpx、PyJWT、Pillow

**Storage**: PostgreSQL 16（業務資料）；同機檔案系統資料卷（照片，路徑存 DB，經後端代理存取）

**Testing**: pytest + testcontainers（後端單元／整合）、辨識服務 stub（契約）、Vitest + React Testing Library（前端單元）、Playwright（端對端，兩種入口各一輪）

**Target Platform**: 單台 Linux 伺服器（後端、資料庫同機；**辨識服務為第三方代管雲端 API，非同機部署**，見 [research.md](./research.md) R-16）；前端為行動優先網頁，需同時運作於 LINE App 內建瀏覽器（LIFF）與一般手機／桌機瀏覽器

**Project Type**: Web application（frontend + backend 分離目錄，共用同一後端 API）

**Performance Goals**:

- 份量調整後畫面重算 < 0.3 秒（SC-003）——以純前端計算達成，調整期間不得有任何 API 呼叫
- 儀表板／趨勢查詢在 30 天區間、單一使用者資料量下 < 500 ms
- 辨識等待上限 30 秒（暫定，OQ-4；辨識服務為外部雲端 API，門檻需依實測公網延遲重新校準，見 research.md R-16）

**Constraints**:

- 客戶端不保留離線資料，所有資料即時取自後端（憲章原則 III）
- 後端驗證邏輯不因入口分岔（憲章原則 I）
- 前端不得假設執行於 LIFF context（憲章原則 II）
- 通用食物營養對照表不得與店家／餐點資料共用資料表或建立外鍵（憲章原則 V）
- 同步呼叫不得寫死成無法更改的架構決定（brief 明確要求）

**Scale/Scope**: MVP 約 25 位使用者，每人每日約 5 次辨識（約 125 次／日）；前端約 6 個頁面路由 + 3 個全屏流程（拍照、辨識確認、onboarding）；後端 13 支端點、6 張資料表

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

依 [.specify/memory/constitution.md](../../.specify/memory/constitution.md) v1.0.0 逐條檢核。

| 原則 | 檢核項 | Phase 0 前 | Phase 1 後 | 落實位置 |
|---|---|---|---|---|
| **I. 統一 LINE 登入**（NON-NEGOTIABLE） | 無 Email 帳密註冊／登入路徑 | ✅ | ✅ | 契約中無任何帳密端點 |
| | 兩入口共用同一驗證核心，不分岔 | ✅ | ✅ | [research.md](./research.md) R-03；`verify_line_identity()` 單一函式，`LineIdentity` 不帶入口資訊 |
| **II. 環境自我偵測** | 具備 LIFF 環境判斷能力 | ✅ | ✅ | R-02；`src/lib/liff/environment.ts` |
| | 不假設必然執行於 LIFF、判斷不散落 | ✅ | ✅ | R-02；元件取不到原始 `liff` 物件，只能用包裝函式；`liff.init()` 失敗即降級為正常路徑 |
| **III. 單一後端多客戶端** | 四端共用同一後端、無離線資料 | ✅ | ✅ | [contracts/openapi.yaml](./contracts/openapi.yaml) 無客戶端專屬端點；前端無本地持久化業務資料 |
| | 不開發同步機制 | ✅ | ✅ | 伺服器狀態一律經 TanStack Query 即時取得 |
| **IV. 角色與權限隔離**（NON-NEGOTIABLE） | 建立僅管理員可通過的檢查層 | ✅ | ✅ | R-14；`require_admin()` 依賴 + `users.role` 欄位（本輪不掛載於端點，附單元測試） |
| | 權限判斷在後端；使用者資料隔離 | ✅ | ✅ | [data-model.md](./data-model.md)「資料隔離」；所有查詢帶 `user_id`，跨使用者一律 404 |
| **V. 資料表分離** | 通用食物對照表獨立、無外鍵 | ✅ | ✅ | data-model.md `food_nutrition_references`；本輪 migration 不建立任何店家／餐點資料表 |
| **VI. 技術棧約定** | Next.js + FastAPI + PostgreSQL + YOLO/HF | ✅ | ✅ | 本文件 Technical Context |
| | 不為單一功能引入平行框架／資料庫 | ✅ | ✅ | 未引入訊息佇列、快取層或第二套儲存（R-07 已否決 Celery） |
| **VII. 免責範圍**（NON-NEGOTIABLE） | 不提供醫療診斷；明示為估算值 | ✅ | ✅ | spec FR-057／FR-058；驗證情境 [quickstart.md](./quickstart.md) V10 |

**Gate 結論**：Phase 0 前後皆通過，**無違規項**，Complexity Tracking 無需填寫。

兩項憲章明列的必測情境已排入測試策略（R-15）：

- 「一般使用者存取管理端 API 被拒絕」→ `require_admin()` 單元測試 + 跨使用者存取整合測試（quickstart V9）
- 「非 LIFF 環境可完成登入流程」→ 環境模組降級單元測試 + Playwright 一般瀏覽器 OAuth 流程（quickstart V1）

## Project Structure

### Documentation (this feature)

```text
specs/001-diet-log-mvp/
├── plan.md                          # 本檔（/speckit.plan 輸出）
├── spec.md                          # 功能規格（/speckit.specify 輸出）
├── research.md                      # Phase 0：15 項技術決策 + Open Questions
├── data-model.md                    # Phase 1：6 張資料表、索引、狀態轉換
├── quickstart.md                    # Phase 1：環境設定與 10 組驗證情境
├── contracts/
│   ├── openapi.yaml                 # 後端對外 API 契約（13 端點）
│   └── recognition-service.md       # 後端所消費的辨識服務契約（已確認，OQ-3 關閉）
├── checklists/
│   └── requirements.md              # 規格品質檢查
└── tasks.md                         # Phase 2（/speckit.tasks 產出，本指令不建立）
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                      # FastAPI app、CORS、錯誤處理器註冊
│   ├── api/v1/
│   │   ├── auth.py                  # /auth/line/liff、/auth/line/callback
│   │   ├── profile.py               # /me、/me/profile
│   │   ├── recognitions.py          # /recognitions、/{id}、/{id}/retry
│   │   ├── meal_records.py          # CRUD + /photo
│   │   ├── analytics.py             # /dashboard、/trends
│   │   └── foods.py                 # /foods/search
│   ├── core/
│   │   ├── config.py                # 環境變數（Pydantic Settings）
│   │   ├── security.py              # JWT 簽發與解析
│   │   ├── deps.py                  # get_current_user()、require_admin()
│   │   ├── errors.py                # 錯誤信封、code → HTTP 對照
│   │   └── clock.py                 # Asia/Taipei 日期歸屬
│   ├── db/
│   │   ├── session.py
│   │   └── models/                  # users, health_profiles, meal_records,
│   │                                # meal_items, food_nutrition_references,
│   │                                # recognition_jobs
│   ├── schemas/                     # Pydantic 請求／回應模型（對齊 openapi.yaml）
│   ├── services/
│   │   ├── line_auth.py             # ★ 單一驗證核心（憲章原則 I）
│   │   ├── targets.py               # BMR/TDEE 與營養素目標計算
│   │   ├── nutrition.py             # per_100g × grams / 100 換算與驗算
│   │   ├── recognition_client.py    # ★ 辨識服務 adapter（唯一接觸點，OQ-3 隔離）
│   │   ├── photo_storage.py         # 檔案系統存取抽象
│   │   └── analytics.py             # 儀表板／趨勢聚合、日期序列補零
│   └── scripts/seed_foods.py        # 通用食物營養對照表匯入（OQ-2）
├── alembic/versions/
└── tests/
    ├── unit/                        # 公式、換算、錯誤映射、require_admin
    ├── integration/                 # 端點授權、資料隔離、辨識各分支
    └── contract/                    # 對辨識 stub 的契約測試

frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx               # 主題初始化（避免深色模式閃爍）
│   │   ├── login/page.tsx
│   │   ├── auth/callback/page.tsx   # 網頁 OAuth 回呼
│   │   ├── onboarding/page.tsx      # 多步驟建檔 + TDEE 結果
│   │   └── (app)/
│   │       ├── layout.tsx           # 底部導覽列、登入守衛
│   │       ├── dashboard/page.tsx
│   │       ├── trends/page.tsx
│   │       ├── profile/page.tsx
│   │       └── capture/page.tsx     # 拍照 → Loading → 確認／錯誤
│   ├── components/
│   │   ├── dashboard/               # 熱量主卡、營養素卡、日期條、餐點清單
│   │   ├── capture/                 # ★ PortionSlider、RecognitionItemCard、
│   │   │                            #   LoadingState、EmptyResultGuide、ErrorState
│   │   ├── trends/
│   │   └── ui/                      # 依 prototype 視覺語彙重建的基礎元件
│   ├── lib/
│   │   ├── liff/environment.ts      # ★ 環境判斷與能力包裝（憲章原則 II）
│   │   ├── api/                     # 型別化 API client（由 openapi.yaml 產生型別）
│   │   └── nutrition.ts             # ★ 前端即時換算（與後端同一公式）
│   ├── hooks/
│   │   └── useRecognition.ts        # ★ status 狀態機（預留 processing 分支）
│   └── styles/                      # Tailwind theme（prototype 色彩／圓角／陰影）
└── tests/{unit,e2e}/

tools/recognition-stub/              # 可切換模式的假辨識服務（normal/empty/timeout/
                                     # error/garbage/unknown_label）
docker-compose.yml                   # postgres + recognition-stub
```

**Structure Decision**: 採前後端分離的雙目錄結構（`backend/` + `frontend/`）。理由：兩者語言與工具鏈完全不同（Python／Node），且憲章原則 III 要求後端服務多個客戶端——第二輪的 Flutter 專案會是第三個獨立目錄，與現有兩者平行。目前不引入 monorepo 工具（Turborepo／Nx），因為跨專案共用的只有型別定義，而型別可由 `contracts/openapi.yaml` 產生，不需要建置編排層。

上表以 ★ 標記的檔案是本輪的**架構關鍵點**——每一個都對應一條不可妥協的需求或憲章原則，實作時若偏離會導致返工：

| 檔案 | 承載的約束 |
|---|---|
| `services/line_auth.py` | 憲章原則 I：兩入口單一驗證核心 |
| `lib/liff/environment.ts` | 憲章原則 II：環境判斷收斂、不假設 LIFF |
| `services/recognition_client.py` | OQ-3 的變更隔離；辨識契約若有出入只改這裡（本輪已用於吸收真實外部 API 與假定契約的差異，見 research.md R-16） |
| `hooks/useRecognition.ts` | R-07：預留 `processing` 分支，非同步遷移不需改畫面 |
| `lib/nutrition.ts` + `components/capture/PortionSlider` | FR-031〜034、SC-003：份量即時重算，調整期間零 API 呼叫 |
| `components/capture/EmptyResultGuide` | FR-027：`items: []` 走成功路徑的專屬引導畫面 |

## 關鍵架構決策摘要

完整論證見 [research.md](./research.md)，此處摘錄影響最大的五項：

1. **辨識 API 採資源導向而非函式導向**（R-07）。即使本輪同步實作，回應永遠是 `{id, status, items, message}` 並提供 `GET /recognitions/{id}`。前端 `useRecognition()` 以 `status` 驅動畫面，`processing` 分支先寫好但暫不會觸發。非同步遷移的成本因此侷限於「後端一支端點的回應時機」與「前端一個 hook 的取得方式」，畫面層、資料模型與對外契約皆不需破壞性變更。

2. **`items: []` 是成功而非錯誤**（R-08）。走 HTTP 200、`recognition_jobs.status = 'completed'`、`item_count = 0`。若歸為錯誤，前端會落入通用錯誤處理而渲染空清單——正是 FR-027 明文禁止的行為。

3. **對外回應必須帶 `per_100g`，由後端 adapter 反推**（R-09）。這是「份量調整不呼叫後端」的必要條件。本輪實際串接的外部辨識 API 只提供估計份量下的絕對值，`per_100g` 由 `recognition_client.build_items()` 反推得出，前端契約與計算邏輯因此不需改動。儲存時後端以同一公式重新驗算，客戶端數值不採信。

4. **`meal_items` 儲存營養值快照**（R-11）。日後修正營養對照表不得追溯改變歷史紀錄與趨勢圖；`food_reference_id` 為弱關聯（`ON DELETE SET NULL`）。辨識路徑產生的品項現一律 `food_reference_id = null`（新服務的營養值不再經由對照表換算）。

5. **辨識服務為外部代管 API，契約差異收斂於單一 adapter**（R-16）。`services/recognition_client.py` 是與此服務的唯一接觸點；`X-API-Key` 認證、`estimated_weight_g`／絕對營養值格式、無 Top-K 候選等真實契約細節皆隔離在此檔案內，`recognition_jobs`、對外 API 契約（`openapi.yaml`）與前端皆不受影響。

## Open Questions

| ID | 問題 | 現行假設 | 需在何時決定 |
|---|---|---|---|
| **OQ-1** | **辨識服務為同步或非同步？回應時間 p95？** | **同步 HTTP，逾時 30s；p95 待實測，須涵蓋外部服務公網延遲（R-16）** | **實作辨識串接前** |
| OQ-2 | 通用食物營養對照表的資料來源與涵蓋範圍 | 本輪自建，供 FR-037 手動搜尋使用（不再是辨識換算的必經路徑） | 資料表建立前 |
| ~~OQ-3~~ | ~~辨識服務的實際 HTTP 介面~~ | **已確認關閉（2026-08-04）**，見 [contracts/recognition-service.md](./contracts/recognition-service.md)、research.md R-16 | 已解決 |
| OQ-4 | 逾時門檻 30 秒是否合適 | 30s，需依外部服務實測回應時間重新校準 | 取得 OQ-1 實測後 |
| OQ-5 | 照片保留期限與刪除政策 | 刪除紀錄時同步刪除照片檔案 | 上線前 |
| OQ-6 | Rich Menu 分流方式（同一前端不同路由 vs 兩組 LIFF） | 本輪不決定 | 第二輪 plan |
| OQ-7 | 個人健康檔案是否納入「性別」欄位 | 納入（BMR 公式所需） | 資料表建立前 |
| OQ-8 | 年齡以「歲數」或「出生日期」儲存 | 歲數（與 prototype 一致） | 資料表建立前 |
| OQ-9 | `RECOGNITION_API_KEY` 正式環境輪替流程 | 本輪僅手動輪替，無自動化機制 | 上線前 |

**OQ-1 為 brief 指定必須標註的待確認技術假設**。非同步遷移的完整影響評估見 [research.md](./research.md) R-07 的對照表，結論為：現行 API 設計可在不破壞契約的前提下遷移。

## 本輪不處理（留給後續 plan）

- 推薦餐廳模組（定位、店家清單、餐點瀏覽）及其資料表——第二輪
- 管理員角色的後台介面與維護端點——本輪僅預留 `users.role` 與 `require_admin()` 骨架
- Flutter iOS／Android 客戶端與 LINE 原生 SDK 串接——後續輪次
- LINE Messaging API 訊息推播
- Rich Menu 分流的技術選型（OQ-6）

## Complexity Tracking

Constitution Check 於 Phase 0 前與 Phase 1 後**皆無違規項**，本節無需填寫。

設計過程中被明確否決的複雜度（詳見 research.md）：訊息佇列／背景 worker（R-07）、全域狀態管理庫（R-01）、物件儲存服務（R-10）、refresh token 機制（R-04）、完整 RBAC 權限表（R-14）、monorepo 建置編排（Structure Decision）。每一項的否決理由均為「本輪規模下成本超過收益，且未來加入不需破壞性變更」。
