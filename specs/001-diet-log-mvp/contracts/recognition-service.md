# Contract: 內部 AI 辨識服務

**Date**: 2026-08-03 | **Plan**: [../plan.md](../plan.md)

本文件描述後端所**消費**的介面（辨識服務），與 [openapi.yaml](./openapi.yaml) 描述的「後端所提供」的介面是兩件事。

## 部署與呼叫模型

- 辨識服務與 FastAPI 主程式部署於**同一台伺服器**，屬內部服務呼叫。
- 不經公網、不跨網域、不使用第三方 Hugging Face Inference Endpoint。
- 後端以 `httpx.AsyncClient` 呼叫，逾時 `RECOGNITION_TIMEOUT_SECONDS`（預設 30）。
- 後端**不做自動重試**；重試由使用者顯式觸發（見 [../research.md](../research.md) R-08）。

## ⚠️ 契約狀態：假定（OQ-3）

目前**唯一經確認**的部分是錯誤／空結果的回傳格式：

```json
{
  "items": [],
  "message": "沒有偵測到食物，請換一張再試試"
}
```

其餘欄位（成功回應的完整結構、是否回傳 Top-K 候選、是否回傳 bounding box、端點路徑與請求格式）**均為依模型行為推導的假定**，需在實作前與模型端確認。

**隔離措施**：所有與此契約的接觸點集中在 `backend/app/services/recognition_client.py` 一個 adapter 模組。實際契約若與此處假定不同，改動範圍限於該模組的解析邏輯 + 對應的 stub 服務；`recognition_jobs` 資料表、[openapi.yaml](./openapi.yaml) 的對外契約與前端皆不受影響。

## 假定請求

```http
POST {RECOGNITION_SERVICE_URL}/predict
Content-Type: multipart/form-data

photo: <binary>
```

| 參數 | 說明 |
|---|---|
| `photo` | 使用者上傳的完整照片（後端已壓縮至最長邊 1280px） |

模型內部流程（YOLO 偵測 → 裁切 → HF 分類）對後端不可見，後端只消費最終輸出。

## 假定成功回應

```jsonc
{
  "items": [
    {
      "label": "braised_pork_rice",        // 對應 food_nutrition_references.model_label
      "confidence": 0.93,
      "bbox": { "x": 120, "y": 88, "width": 420, "height": 380 },
      "candidates": [                        // HF Top-K，依信心度排序
        { "label": "braised_pork_rice", "confidence": 0.93 },
        { "label": "braised_pork_belly_rice", "confidence": 0.05 },
        { "label": "minced_pork_rice", "confidence": 0.02 }
      ]
    }
  ],
  "message": null
}
```

**明確不提供的資訊**：份量、克數、重量、體積。HF 分類模型無法估算份量——這是本輪份量流程改採「系統預設值 + 使用者調整」的根本原因（[../spec.md](../spec.md) FR-022）。後端**不得**期待此回應中出現任何份量欄位。

## 後端的轉換責任

辨識服務回傳的是**分類標籤**，不是營養資訊。後端負責：

| 步驟 | 動作 | 失敗時 |
|---|---|---|
| 1 | 以 `label` 查 `food_nutrition_references.model_label` | 查無 → 該品項 `nutrition_available: false`，仍列出名稱（FR-037） |
| 2 | 取得該食物的 `per_100g` 與 `default_portion_grams` | — |
| 3 | 對 `candidates` 逐一查表，組成前端可改選的候選清單 | 查無的候選其 `per_100g` 為 null |
| 4 | 組成 [openapi.yaml](./openapi.yaml) 的 `Recognition` 資源回傳前端 | — |

`per_100g` **必須**進入回應——前端要靠它做份量即時換算而不再呼叫後端（R-09）。

## 情境對照表

| 辨識服務行為 | 後端判定 | `recognition_jobs.status` | 對外 HTTP | 對外 code |
|---|---|---|---|---|
| 200 + `items` 非空 | 成功 | `completed` | 200 | — |
| 200 + `items: []` + `message` | **成功**（未偵測到食物） | `completed`，`item_count = 0` | 200 | — |
| 超過逾時仍未回應 | 失敗 | `failed`，`error_code = TIMEOUT` | 504 | `RECOGNITION_TIMEOUT` |
| 5xx | 失敗 | `failed`，`error_code = UNAVAILABLE` | 503 | `RECOGNITION_UNAVAILABLE` |
| 連線被拒／DNS 失敗 | 失敗 | `failed`，`error_code = UNAVAILABLE` | 503 | `RECOGNITION_UNAVAILABLE` |
| 200 但 JSON 無法解析或缺 `items` | 失敗 | `failed`，`error_code = BAD_RESPONSE` | 502 | `RECOGNITION_BAD_RESPONSE` |

**最關鍵的一列是第二列**：`items: []` 走**成功**路徑，不是錯誤路徑。若把它歸為錯誤，前端會落入通用錯誤處理而渲染出空的結果清單——正是 spec FR-027 明文禁止的行為。

## 本機開發用 Stub

實作 `tools/recognition-stub/` 提供可切換模式的假服務，讓錯誤處理路徑在真服務就緒前即可完整驗證：

| 模式（`?mode=`） | 行為 |
|---|---|
| `normal`（預設） | 回傳 2–3 個品項，含 Top-K 候選 |
| `empty` | 回傳 `{"items": [], "message": "沒有偵測到食物，請換一張再試試"}` |
| `timeout` | 延遲 60 秒後才回應（觸發後端逾時） |
| `error` | 回 500 |
| `garbage` | 回傳非 JSON 內容 |
| `unknown_label` | 回傳不存在於營養對照表的 label（驗證 `nutrition_available: false` 路徑） |

此 stub 亦作為契約測試的對象（[../research.md](../research.md) R-15）。

## 非同步遷移時的變化

若 OQ-1 確認改為非同步，本文件的變化僅限於：

- 請求端點可能改為「提交 → 取得 job id」＋「查詢 job 結果」兩支。
- `recognition_client.py` 由「呼叫並等待」改為「提交」與「查詢」兩個方法。

`recognition_jobs` 資料表已具備 `status`、`completed_at`、`error_code`、`duration_ms` 欄位，不需 schema 變更；對外 API 契約亦不需破壞性變更（詳見 [../research.md](../research.md) R-07 的遷移影響評估表）。
