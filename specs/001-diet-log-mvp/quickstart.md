# Quickstart: 拍照飲食紀錄 MVP（第一輪）

**Date**: 2026-08-03 | **Plan**: [plan.md](./plan.md)

本文件是**驗證指南**——如何把本輪功能跑起來，以及如何證明它真的照 [spec.md](./spec.md) 運作。實作細節屬 `tasks.md` 與實作階段，此處不重複。

## 前置需求

| 項目 | 版本 | 備註 |
|---|---|---|
| Node.js | 20 LTS | 前端 |
| Python | 3.12 | 後端 |
| PostgreSQL | 16 | 可用 Docker 起 |
| Docker | 任意近期版本 | 起 PostgreSQL 與辨識 stub |
| LINE Developers 帳號 | — | 需 LINE Login channel + LIFF app（OQ-6 之外的基本設定） |

## 環境變數

**後端** `backend/.env`

```bash
DATABASE_URL=postgresql+psycopg://caluli:caluli@localhost:5432/caluli
JWT_SECRET=<隨機字串>
JWT_EXPIRES_SECONDS=604800

LINE_CHANNEL_ID=<LINE Login channel ID>
LINE_CHANNEL_SECRET=<LINE Login channel secret>

RECOGNITION_SERVICE_URL=http://localhost:8900      # 本機／CI 指向 stub；正式環境改為 https://taiwanese-food-api-528488788338.asia-east1.run.app
RECOGNITION_API_KEY=<外部辨識 API 的 X-API-Key；本機打 stub 時可留空>
RECOGNITION_TIMEOUT_SECONDS=30      # 暫定值，待 OQ-1／OQ-4 確認（正式環境需涵蓋外部服務公網延遲，見 research.md R-16）

PHOTO_STORAGE_ROOT=./var/photos
PHOTO_MAX_BYTES=10485760
APP_TIMEZONE=Asia/Taipei
```

**前端** `frontend/.env.local`

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_LIFF_ID=<LIFF app ID>
NEXT_PUBLIC_LINE_CHANNEL_ID=<同上 channel ID，供網頁 OAuth 用>
NEXT_PUBLIC_LINE_REDIRECT_URI=http://localhost:3000/auth/callback
```

## 啟動

```bash
# 1. 資料庫
docker compose up -d postgres

# 2. 後端
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed_foods       # 匯入通用食物營養對照表（見 OQ-2）
uv run uvicorn app.main:app --reload --port 8000

# 3. 辨識服務 stub（真服務就緒前使用）
cd tools/recognition-stub && uv run uvicorn stub:app --port 8900

# 4. 前端
cd frontend
npm install
npm run dev                                    # http://localhost:3000
```

API 文件：<http://localhost:8000/docs>（由 [contracts/openapi.yaml](./contracts/openapi.yaml) 對照驗證）

## 測試

```bash
# 後端：單元 + 整合（整合測試以 testcontainers 起真 PostgreSQL）
cd backend && uv run pytest

# 前端：單元
cd frontend && npm run test

# 端對端：兩種入口各走一次完整流程
cd frontend && npm run test:e2e
```

---

## 驗證情境

每個情境對應 [spec.md](./spec.md) 的一個 user story 或關鍵需求。**逐一走過即可證明本輪功能完整**。

### V1 — 一般瀏覽器登入與首次建檔（US1 / FR-002, FR-004, FR-013）

1. 以一般瀏覽器（非 LINE App）開啟 <http://localhost:3000>。
2. **預期**：顯示「使用 LINE 登入」按鈕，而非空白或錯誤。`liff.init()` 失敗時應靜默降級為 web 模式。
3. 點擊登入 → 完成 LINE 授權 → 回到服務。
4. **預期**：因尚無 health profile，自動導向個人資訊填寫流程，且無法直接以網址跳到 `/dashboard`。
5. 依序填入性別、年齡、身高、體重、活動量 → 送出。
6. **預期**：顯示每日建議總熱量與蛋白質／碳水／脂肪目標。以 [research.md](./research.md) R-13 的公式手算比對，數值須一致。

### V2 — LIFF 入口登入（US1 / FR-003）

1. 於 LINE Developers 將 LIFF endpoint 指向本機（需 HTTPS 通道，例如 ngrok）。
2. 從 LINE App 開啟該 LIFF URL。
3. **預期**：無需任何點擊即完成登入；已建檔者直接進入儀表板。
4. **預期**：與 V1 為同一 LINE 帳號時，看到的是**同一份資料**（FR-007、SC-006）。

### V3 — 拍照辨識與份量即時調整（US2 / FR-025, FR-031〜FR-034）★ 核心

1. 儀表板點「拍照記帳」→ 選擇相簿上傳一張餐點照片（stub 模式 `normal`）。
2. **預期**：送出後畫面持續顯示「分析中」狀態，且送出按鈕不可重複點擊。
3. **預期**：結果畫面逐項列出食物名稱、份量（公克）、熱量與三大營養素，並顯示合計。
4. 拖動任一項的份量滑桿（例如 250g → 375g）。
5. **預期**：該項熱量與營養素**立即**更新（無網路請求、無「重新計算」按鈕），合計同步變動。
   - 驗證方式：開啟瀏覽器 Network 分頁，調整份量期間**不應有任何 API 呼叫**。
   - 數值驗證：`per_100g × 375 / 100`。
6. 點某項的「修正名稱」，改用通用食物對照表搜尋並選擇其他食物（本輪辨識服務不提供候選清單，修正入口為搜尋而非候選改選，見 research.md R-16）。
7. **預期**：改以新食物的 `per_100g` 與 `default_portion_grams` 重新換算。
8. 移除一項誤判品項 → **預期**：不列入合計。
9. 儲存 → **預期**：返回儀表板，今日已攝取與剩餘熱量已含此筆，**無需手動重新整理**（FR-041）。

### V4 — 未偵測到食物（FR-027）★ 最易誤實作

1. 將 stub 切至 `empty` 模式後上傳照片。
2. **預期**：顯示引導畫面，內容為後端合成的固定文案「沒有偵測到食物，請換一張再試試」（外部辨識服務本身不提供說明文字，見 [contracts/recognition-service.md](./contracts/recognition-service.md)），並提供「重新拍攝」與「返回」。
3. **預期**：**不得**出現空的結果清單、空白畫面或通用錯誤畫面。
4. **預期**：後端 `recognition_jobs` 該筆 `status = 'completed'`、`item_count = 0`（**不是** `failed`）。

### V5 — 辨識錯誤與重試（FR-028, FR-029）

| stub 模式 | 預期 HTTP | 預期畫面 | 重試行為 |
|---|---|---|---|
| `timeout` | 504 `RECOGNITION_TIMEOUT` | 逾時說明 + 「重試」 | 點重試**不需重新選照片**，走 `POST /recognitions/{id}/retry` |
| `error` | 503 `RECOGNITION_UNAVAILABLE` | 服務忙碌說明 + 「重試」 | 連續 3 次失敗後另外出現「返回」 |
| `unauthorized` | 503 `RECOGNITION_UNAVAILABLE` | 同上（`X-API-Key` 問題對使用者呈現為服務不可用，不揭露認證細節） | 同上 |
| `garbage` | 502 `RECOGNITION_BAD_RESPONSE` | 同上，且不外露技術細節 | 同上 |
| `zero_weight` | 200 | 品項列出但標示「無法自動換算」，可自行填入或移除（`estimated_weight_g = 0` 時無法反推 per_100g，見 research.md R-16） | — |

另驗證：上傳非圖片檔 → 415；上傳 >10MB 檔案 → 413，兩者皆在送出辨識前即被擋下。

### V6 — 儀表板（US3 / FR-045〜FR-050）

1. 當日無紀錄 → **預期**：已攝取 0、剩餘 = 每日建議熱量、顯示空狀態。
2. 建立數筆紀錄 → **預期**：已攝取 = 各筆合計；剩餘 = 建議 − 已攝取。
3. 刻意超標 → **預期**：明確標示已超出目標。
4. 切「尚缺」視角 → **預期**：改以距離目標的差額呈現。
5. 切到前一日 → **預期**：顯示該日資料，當日資料不受影響。

### V7 — 趨勢圖表（US4 / FR-051〜FR-055）

1. 造出跨多日、且中間有空白日的紀錄。
2. 切換 7／14／30 天與四種指標。
3. **預期**：各日數值等於該日紀錄合計；**空白日顯示 0 而非斷線或報錯**。
4. 全新帳號開啟趨勢頁 → **預期**：空狀態說明 + 引導建立第一筆紀錄。

### V8 — 資料維護與目標重算（US5 / FR-015, FR-016, FR-042, FR-043）

1. 設定頁改體重 → **預期**：每日建議熱量與營養素目標隨之改變。
2. 查看**過去日期**的儀表板 → **預期**：歷史攝取數值**未改變**（快照生效，[research.md](./research.md) R-11）。
3. 編輯某筆既有紀錄的份量 → **預期**：該筆與該日合計同步更新。
4. 刪除某筆 → **預期**：清單移除、該日合計與趨勢圖同步扣除、照片檔案一併刪除。

### V9 — 資料隔離（FR-044, SC-009，憲章原則 IV）

1. 以帳號 A 建立紀錄，記下 `record_id`。
2. 以帳號 B 的 token 呼叫 `GET /api/v1/meal-records/{A的record_id}/photo` 與 `PATCH /api/v1/meal-records/{A的record_id}`。
3. **預期**：兩者皆回 `404`（刻意不回 403，避免洩漏資源存在性）。
4. 呼叫任何端點時把 `require_admin` 依賴掛上 → **預期**：一般使用者 token 被拒。
   （本輪無管理端端點，此項以單元測試驗證 `require_admin()` 本身。）

### V10 — 免責呈現（FR-057, FR-058，憲章原則 VII）

1. 檢視辨識結果畫面與儀表板。
2. **預期**：明確可見「數值為估算參考」之說明。
3. **預期**：全站無任何疾病判讀、過敏建議、處方或醫療效力暗示的文案。

---

## 已知限制（本輪）

- 辨識服務介面已確認（OQ-3 關閉，見 [contracts/recognition-service.md](./contracts/recognition-service.md)、research.md R-16）；上述 V3〜V5 以 stub 驗證，正式環境串接真實外部 API 後應至少重跑一次 V3、V4、V5（含 401 情境）確認行為一致。
- 逾時門檻 30 秒為暫定值（OQ-4），需以 `recognition_jobs.duration_ms` 的實測分布（涵蓋外部服務公網延遲）回頭校準。
- 通用食物營養對照表僅供 FR-037 手動搜尋修正名稱使用（OQ-2 決定其涵蓋範圍）；辨識服務目前僅涵蓋 101 類台灣小吃，不在此範圍的食物一律呈現為未偵測到（V4 情境）。
- `RECOGNITION_API_KEY` 輪替目前僅為手動流程（OQ-9），無自動化機制。
- 無管理員後台、無推薦餐廳、無 Flutter 客戶端——皆屬後續輪次。
