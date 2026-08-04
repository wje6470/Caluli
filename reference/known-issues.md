# 已知問題登記簿

跨輪次的技術債與待處理問題。每一項都應記錄：**現況、為什麼還沒壞、什麼時候會壞、改動範圍、驗證方式**，讓接手的人不必重新調查。

---

## KI-001：第一輪的數值欄位回傳字串，但型別宣告是 number

| | |
|---|---|
| **發現於** | 2026-08-04，第三輪與第二輪對齊數值型別時 |
| **狀態** | 🟡 未修復。**目前不會壞，但沒有任何機制防止它壞** |
| **決定** | 合併完成後再處理（2026-08-04） |
| **影響範圍** | 第一輪的 4 個 schema 檔；第二、三輪已於 2026-08-04 改為 JSON number |

### 問題

第一輪的回應 schema 以 `Decimal` 宣告欄位，而 **pydantic v2 會把 `Decimal` 序列化成字串**：

```
GET /api/v1/me/profile
{"height_cm":"175.0","weight_kg":"68.5","tdee_kcal":"2368.94", ...}
              ↑ 字串，不是數字
```

但同一組欄位在兩處都宣告為數字：

- `specs/001-diet-log-mvp/contracts/openapi.yaml` → `type: number`
- `frontend/src/lib/api/types.ts` → `height_cm: number`

**TypeScript 完全不會警告**，因為它相信型別宣告。

### 為什麼現在沒壞（重要，不要重新調查）

JS 有兩類寫法，對字串的容忍度完全不同：

| 寫法 | 遇到字串 | 第一輪是否使用 |
|---|---|---|
| `Math.round(x)` / `Math.max()` / `Math.min()` | ✅ 隱式轉型，結果正確 | ✅ 大量使用 |
| `x * factor`、`x / y` | ✅ 隱式轉型 | ✅ 使用 |
| `a + b`（加總） | ❌ **變成字串串接，產生錯誤數字且不報錯** | ⚠️ 有，但見下 |
| `x.toFixed(1)` / `x.toLocaleString()` | ❌ **TypeError，整頁崩潰** | ❌ **沒有直接用在 API 值上** |

唯一的加總在 `frontend/src/lib/nutrition.ts` 的 `sumNutrients()`：

```ts
calories_kcal: total.calories_kcal + item.calories_kcal   // 字串會串接
```

但它的兩個呼叫端（`capture/page.tsx:55`、`MealEditSheet.tsx:51`）都**先經過 `scaleNutrients()`**，而該函式做的是 `per100g.calories_kcal * factor`——乘法先把字串轉成數字，所以到加總時已經是真正的數字。

`formatGrams()` 也一樣：`(Math.round(value * 10) / 10).toFixed(1)`，`value * 10` 先轉型，`.toFixed()` 才安全。

**結論：每一條路徑都恰好避開了地雷，但那是碰巧，不是設計。**

### 什麼時候會壞

下一個人只要寫出這樣一行：

```ts
profile.weight_kg.toFixed(1)        // TypeError: toFixed is not a function
```

型別宣告說它是 `number`，IDE 會自動補完 `.toFixed()`，編譯通過，上線後整頁白畫面。

**第二輪已經真的踩過這個雷**：`MenuItemRow` 對 `"650.00"` 呼叫 `.toFixed(1)`，整頁崩潰。

風險會隨時間上升：Flutter（憲章原則 VI）進來後，Dart 是強型別，收到字串會直接 parse 失敗而非默默轉型。

### 改動範圍

需要改的是**輸出 schema**（輸入 schema 可維持 `Decimal`，pydantic 會轉換）：

| 檔案 | 類別 | 欄位數 |
|---|---|---|
| `app/schemas/profile.py` | `HealthProfileOut` | 7 |
| `app/schemas/meal_record.py` | `MealItemOut` | 2 |
| `app/schemas/meal_record.py` | `Nutrients`（被多處嵌入） | 4 |
| `app/schemas/analytics.py` | `TrendResponse` | 3 |
| `app/schemas/analytics.py` | `TrendPoint` | 1 |
| `app/schemas/recognition.py` | `Per100g`、`FoodCandidate`、`RecognitionItem`、`FoodReferenceOut` | 7 |

合計約 **24 個輸出欄位**。輸入 schema（`HealthProfileInput` 2 個、`MealItemInput` 2 個）不需要動。

前端**預期零處需要調整**——現有寫法都已經在做隱式轉型，改成真數字後行為完全相同。

### 為什麼改動比看起來安全

前端所有消費端都已經把這些值當數字用（乘、除、`Math.*`）。把後端改成真的回數字，等於**把隱式轉型移除**，行為不變，只是不再依賴運氣。

### 建議做法

1. 輸出 schema 的 `Decimal` → `float`
2. **加 `isinstance` 型別斷言**——這一步不可省略：

   ```python
   assert isinstance(body["height_cm"], float)
   ```

   第三輪做過突變測試證實：把 schema 改回 `Decimal` 後，**47 支用 `float(x)` 比較的既有測試全部通過**，只有 3 支 `isinstance` 斷言抓到。用 `float(x)` 做斷言對這種退化完全免疫，因為 `float("175.0")` 與 `float(175.0)` 都會通過。

   參考實作：`backend/tests/integration/test_admin_stores.py` 的「JSON 原生型別護欄」區段。
3. 前端型別維持 `number`（本來就宣告對了，只是實作沒跟上）
4. 跑完整回歸：`pytest` + 前端 `tsc` / `vitest` / `build`

### 為什麼第三輪沒有一併修

`specs/003-admin-backoffice/spec.md` 的 **FR-043** 明文禁止本輪修改第一輪既有 API 的行為。改動回應的型別屬於行為變更，需另開輪次或取得明確授權。

### 相關記錄

- `reference/round2-to-round3-sync.md` — 第二輪回報他們踩到 `.toFixed()` 崩潰
- `reference/round3-to-round2-merge.md` 注意事項 2 — 雙方定案改為 JSON number 的四點論證
- `specs/003-admin-backoffice/contracts/admin-api.yaml` — 第三輪 schema 的型別說明與理由
