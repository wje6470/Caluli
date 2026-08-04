# Contract: 辨識服務（台灣小吃辨識 API）

**Date**: 2026-08-03（初版，假定契約）｜**Amended**: 2026-08-04（換成真實已確認契約，OQ-3 關閉）｜**Plan**: [../plan.md](../plan.md)

本文件描述後端所**消費**的介面（辨識服務），與 [openapi.yaml](./openapi.yaml) 描述的「後端所提供」的介面是兩件事。

## ✅ 契約狀態：已確認（OQ-3 關閉）

本輪串接的是第三方代管的「台灣小吃辨識 API」，已取得官方文件確認，非原先假定的同機內部服務。與初版假定契約的關鍵差異：

| 項目 | 初版假定 | 實際契約 |
|---|---|---|
| 部署方式 | 同機內部呼叫，不經公網 | **第三方雲端服務**（`asia-east1.run.app`），經公網呼叫 |
| 端點路徑 | `POST /predict` | `POST /api/detect` |
| 認證 | 無 | **`X-API-Key` header，單一固定金鑰** |
| 上傳欄位名 | `photo` | `file` |
| 回應內容 | 分類標籤 + Top-K 候選，**不含營養值** | **直接內含該品項的熱量與三大營養素**（該估計份量下的絕對值），**不含候選清單** |
| 份量 | 不提供 | 提供 `estimated_weight_g`（服務自身估算值，非實測） |
| bbox 格式 | `{x, y, width, height}` | `{x1, y1, x2, y2}`（像素座標） |
| `message` 欄位 | 服務提供空結果說明文字 | **不提供**；空結果僅回傳 `{"items": []}`，說明文字需由後端 adapter 自行合成 |

## 部署與呼叫模型

- 辨識服務為**第三方代管的雲端服務**，經公網以 HTTPS 呼叫；不受本專案部署掌控，可用性與延遲皆為外部依賴。
- 後端以 `httpx.AsyncClient` 呼叫，逾時 `RECOGNITION_TIMEOUT_SECONDS`（預設 30，需依外部服務實測回應時間重新校準——不再有「同機低延遲」的前提，見 [research.md](../research.md) R-16）。
- 後端**不做自動重試**；重試由使用者顯式觸發（見 [research.md](../research.md) R-08）。
- 服務目前無 SLA 保證、無 rate limit（無 429），一次請求僅能辨識一張照片，無 batch 端點。

## 服務網址與認證

| 項目 | 內容 |
|---|---|
| Base URL | `https://taiwanese-food-api-528488788338.asia-east1.run.app` |
| 端點 | `POST /api/detect`（目前唯一端點，無版本號） |
| 認證方式 | Header `X-API-Key: <key>`；固定金鑰，非 OAuth，缺少或錯誤回 `401` |

金鑰存放於後端環境變數（暫定命名 `RECOGNITION_API_KEY`，實作時於 `app/core/config.py` 定案），**不得**寫死於程式碼或提交進版本控制；錯誤訊息與 log 不得回顯金鑰內容（見 research.md R-16 的金鑰管理決策）。

## 請求

```http
POST https://taiwanese-food-api-528488788338.asia-east1.run.app/api/detect
X-API-Key: <key>
Content-Type: multipart/form-data

file: <binary>
```

| 參數 | 說明 |
|---|---|
| `file` | 使用者上傳的照片（後端已壓縮至最長邊 1280px），僅接受 JPG／PNG，10MB 上限 |

模型內部流程（YOLO 偵測 → 分類 → 對照庫查營養值）對後端不可見，後端只消費最終輸出。

## 成功回應（200）

```json
{
  "items": [
    {
      "name": "滷肉飯",
      "estimated_weight_g": 250,
      "calories": 535.0,
      "protein_g": 20.0,
      "carbs_g": 60.0,
      "fat_g": 22.5,
      "confidence": 0.93,
      "class_name": "braised_pork_over_rice",
      "bbox": { "x1": 120, "y1": 80, "x2": 340, "y2": 260 }
    }
  ]
}
```

### 欄位說明

| 欄位 | 說明 |
|---|---|
| `name` | 食物中文名稱，可直接顯示，不需再查內部對照表 |
| `estimated_weight_g` | 服務自身估算的份量（公克），**非實測值**，對應本輪 spec FR-022 的「初始估計份量」 |
| `calories` | 熱量（大卡），為 `estimated_weight_g` 這個份量下的**絕對值**，不是每 100g 值 |
| `protein_g` / `carbs_g` / `fat_g` | 蛋白質／碳水／脂肪（公克），同為該份量的絕對值 |
| `confidence` | 辨識信心度，0～1 之間 |
| `class_name` | 英文分類代號，僅供除錯與 log 比對，不用於營養值查詢 |
| `bbox` | 食物在照片中的位置框，`{x1, y1, x2, y2}` 像素座標（左上、右下兩點），**非**原假定的 `{x, y, width, height}` |

**不提供 Top-K 候選清單**（無 `candidates` 欄位）。原假定契約中「其他候選食物名稱」的修正路徑，本輪改由既有的通用食物對照表搜尋機制承接（spec FR-035／FR-037，`GET /foods/search`）。

## 後端的轉換責任（`recognition_client.build_items()`）

辨識服務回傳的是**已換算好的絕對營養值**，不是分類標籤——這與初版假定相反。後端負責：

| 步驟 | 動作 | 說明 |
|---|---|---|
| 1 | 以 `calories / estimated_weight_g × 100` 等公式反推每 100g 單位值 | 讓對外回應維持 [openapi.yaml](./openapi.yaml) 既有的 `per_100g` 形狀，**前端份量即時換算邏輯（`lib/nutrition.ts`／`PortionSlider`）完全不需改動**——這是本次改動刻意收斂在 adapter 層的核心理由（research.md R-16） |
| 2 | `default_portion_grams` 直接採用 `estimated_weight_g` | 不再查內部 `food_nutrition_references` 取得系統預設份量 |
| 3 | `food_reference_id` 一律設為 `null` | 新契約的 `class_name` taxonomy 不保證對應內部對照表的 `model_label`，且營養值已由服務直接提供，不再需要對照表關聯來換算 |
| 4 | `nutrition_available` 一律為 `true` | 只要服務回傳該品項，即代表已含完整營養值；僅在防禦性檢查失敗時（見下方邊界情況）才設為 `false` |
| 5 | `candidates` 一律為空陣列 `[]` | 服務不提供 Top-K，前端候選選單需降級為引導使用者改用手動搜尋（FR-035） |
| 6 | `bbox` 座標轉換 | `{x, y, width, height}` = `{x1, y1, x2 - x1, y2 - y1}` |
| 7 | `items` 為空陣列時，由 adapter **自行合成**固定的中文說明文字（例如「沒有偵測到食物，請換一張再試試」），寫入 `recognition_jobs.service_message` | 服務本身不提供 `message` 欄位，此文字需由後端寫死，不依賴上游 |

**邊界情況**：若 `estimated_weight_g` 為 `0`、缺漏或非正數，無法反推每 100g 值——此品項的 `nutrition_available` 設為 `false`、`per_100g` 設為 `null`，仍列出 `name` 供使用者手動修正或移除（沿用 FR-037 的既有降級路徑），不得因單一品項的資料異常而讓整次辨識失敗。

## 情境對照表

| 辨識服務行為 | 後端判定 | `recognition_jobs.status` | 對外 HTTP | 對外 code |
|---|---|---|---|---|
| 200 + `items` 非空 | 成功 | `completed` | 200 | — |
| 200 + `items: []` | **成功**（未偵測到食物，或偵測到但不在101類收錄範圍——兩者無法區分，亦不需區分） | `completed`，`item_count = 0`，`service_message` 由後端合成 | 200 | — |
| 超過逾時仍未回應 | 失敗 | `failed`，`error_code = TIMEOUT` | 504 | `RECOGNITION_TIMEOUT` |
| 5xx（含 `500` 辨識過程異常） | 失敗 | `failed`，`error_code = UNAVAILABLE` | 503 | `RECOGNITION_UNAVAILABLE` |
| `401`（缺少或錯誤 `X-API-Key`） | 失敗 | `failed`，`error_code = UNAVAILABLE` | 503 | `RECOGNITION_UNAVAILABLE`（對使用者呈現為服務暫時不可用，金鑰問題屬維運事項，不對外揭露） |
| `400`（檔案格式／大小） | 理論上不應發生——後端已在上傳階段做同等驗證（FR-019），此處為防禦性處理 | 失敗 | `failed`，`error_code = BAD_RESPONSE` | 502 | `RECOGNITION_BAD_RESPONSE` |
| 連線被拒／DNS 失敗／網路層錯誤 | 失敗 | `failed`，`error_code = UNAVAILABLE` | 503 | `RECOGNITION_UNAVAILABLE` |
| 200 但 JSON 無法解析或缺 `items` | 失敗 | `failed`，`error_code = BAD_RESPONSE` | 502 | `RECOGNITION_BAD_RESPONSE` |

**最關鍵的一列是第二列**：`items: []` 走**成功**路徑，不是錯誤路徑。若把它歸為錯誤，前端會落入通用錯誤處理而渲染出空的結果清單——正是 spec FR-027 明文禁止的行為。

## 本機開發用 Stub

`tools/recognition-stub/` 提供可切換模式的假服務，回應格式對齊上述真實契約（含 `estimated_weight_g`／絕對營養值／`bbox` 的 `{x1,y1,x2,y2}` 格式，不再模擬 `candidates`）：

| 模式（`?mode=`） | 行為 |
|---|---|
| `normal`（預設） | 回傳 2–3 個品項，格式對齊真實 API |
| `empty` | 回傳 `{"items": []}`（無 `message` 欄位，與真實服務一致；由後端 adapter 合成前端顯示文字） |
| `timeout` | 延遲 60 秒後才回應（觸發後端逾時） |
| `error` | 回 500 |
| `unauthorized` | 回 401（模擬缺少／錯誤 `X-API-Key`） |
| `garbage` | 回傳非 JSON 內容 |
| `zero_weight` | 回傳 `estimated_weight_g: 0` 的品項（驗證反推 per_100g 失敗時的降級路徑） |

正式環境呼叫真實外部 API；本機開發與 CI 一律打 stub，避免消耗真實服務的金鑰額度與依賴外部網路穩定性。此 stub 亦作為契約測試的對象（research.md R-15）。

## 非同步遷移時的變化

若未來確認改為非同步，本文件的變化僅限於：

- 後端呼叫方式由「呼叫並等待」改為「提交」與「查詢」兩個方法（`recognition_client.py` 內部）。
- 對此第三方服務本身的請求／回應格式不受影響——非同步與否是**後端與前端之間**的契約，不是後端與此外部服務之間的契約。

`recognition_jobs` 資料表已具備 `status`、`completed_at`、`error_code`、`duration_ms` 欄位，不需 schema 變更；[openapi.yaml](./openapi.yaml) 對外契約亦不需破壞性變更。
