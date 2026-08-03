# Caluli 飲食紀錄 — 第一輪 MVP

拍照分析熱量的 LINE Mini App。使用者從 LINE 官方帳號或一般瀏覽器進入，完成 LINE 登入與個人健康檔案建檔後取得每日熱量目標，拍照交由 AI 辨識食物，套用預設份量換算營養值供**即時調整**後儲存，並以儀表板與趨勢圖表呈現攝取狀況。

> 本服務僅提供熱量與營養素**估算參考**，不提供醫療級營養診斷或治療建議。

## 規格文件

實作前請先讀 [`specs/001-diet-log-mvp/`](specs/001-diet-log-mvp/)：

| 文件 | 內容 |
|---|---|
| [spec.md](specs/001-diet-log-mvp/spec.md) | 功能規格（5 user story、58 條 FR） |
| [plan.md](specs/001-diet-log-mvp/plan.md) | 技術方案、憲章檢核、Open Questions |
| [research.md](specs/001-diet-log-mvp/research.md) | 15 項技術決策與被否決的替代方案 |
| [data-model.md](specs/001-diet-log-mvp/data-model.md) | 6 張資料表 |
| [contracts/](specs/001-diet-log-mvp/contracts/) | 對外 API 契約 + 辨識服務契約 |
| [quickstart.md](specs/001-diet-log-mvp/quickstart.md) | 10 組驗證情境 |
| [tasks.md](specs/001-diet-log-mvp/tasks.md) | 任務清單與實作進度 |

專案的不可協商原則見 [`.specify/memory/constitution.md`](.specify/memory/constitution.md)。

## 技術棧

- **前端** Next.js 15（App Router）+ TypeScript + Tailwind + TanStack Query + Recharts
- **後端** FastAPI + SQLAlchemy 2.0 + Alembic
- **資料庫** PostgreSQL 16
- **AI 辨識** YOLO + Hugging Face（同機部署的內部服務）

## 目錄結構

```
backend/     FastAPI 服務、資料模型、Alembic migration、測試
frontend/    Next.js 應用（LIFF 與一般瀏覽器共用同一份程式碼）
tools/       recognition-stub：可切換模式的假辨識服務
specs/       Spec Kit 規格文件
reference/   產品企劃書、模型資料、UI 原型
```

## 快速開始

前置需求：Node.js 20+、Python 3.12、PostgreSQL 16、[uv](https://docs.astral.sh/uv/)

```bash
# 1. 資料庫（或用既有的 PostgreSQL）
docker compose up -d postgres

# 2. 後端
cd backend
cp .env.example .env          # 填入 LINE channel 設定
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed_foods
uv run uvicorn app.main:app --reload --port 8000

# 3. 辨識服務 stub（真服務就緒前）
cd tools/recognition-stub && uv run uvicorn stub:app --port 8900

# 4. 前端
cd frontend
npm install
npm run dev                    # http://localhost:3000
```

API 文件：<http://localhost:8000/docs>

完整環境變數清單見 [quickstart.md](specs/001-diet-log-mvp/quickstart.md)。

## 測試

```bash
# 後端（整合測試需要 PostgreSQL）
cd backend
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/caluli_test uv run pytest
uv run ruff check .

# 前端
cd frontend
npm run test
npm run typecheck
npm run lint
```

整合測試會依序嘗試 `TEST_DATABASE_URL` → testcontainers（需 Docker）→ skip。

## 三個容易踩的設計約束

實作或重構時特別注意，這些偏離會導致返工：

**1. `items: []` 是成功，不是錯誤**

辨識服務回傳空品項清單代表「照片中沒有食物」，走 HTTP 200、`status=completed`。若歸為錯誤，前端會落入通用錯誤處理而渲染出空清單。詳見 [research.md](specs/001-diet-log-mvp/research.md) R-08。

**2. 辨識回應必須帶 `per_100g`**

份量調整是純前端運算（不呼叫後端），靠的就是這個欄位。移除它，即時調整功能會直接失效。後端在儲存時以同一公式重新驗算，客戶端數值不採信。詳見 R-09。

**3. LIFF SDK 只能在 `src/lib/liff/environment.ts` 內使用**

由 ESLint 的 `no-restricted-imports` 強制。`liff.init()` 失敗一律降級為 web 模式而非拋錯——一般瀏覽器開啟時 init 本來就會失敗，那是正常路徑。詳見憲章原則 II 與 R-02。

## 待確認事項

| ID | 問題 | 現行假設 |
|---|---|---|
| OQ-1 | 辨識服務同步或非同步？回應時間 p95？ | 同步 HTTP，逾時 30s |
| OQ-2 | 通用食物營養對照表的資料來源與涵蓋範圍 | 本輪自建，CSV 匯入 |
| OQ-3 | 辨識服務的實際 HTTP 介面 | 見 contracts/recognition-service.md 的假定契約 |
| OQ-5 | 照片保留期限與刪除政策 | 刪除紀錄時同步刪除照片 |

OQ-1／OQ-3 的變更影響已隔離在 `backend/app/services/recognition_client.py` 單一模組。

## 本輪不含

推薦餐廳模組、管理員後台、Flutter iOS／Android 客戶端、LINE 訊息推播 —— 皆屬後續輪次。
