# Phase 0 Research: 拍照飲食紀錄 MVP（第一輪）

**Date**: 2026-08-03 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

本文件解析 plan 階段的技術未知項，逐項記錄決策、理由與被否決的替代方案。技術棧本身（Next.js／FastAPI／PostgreSQL／YOLO+HF）由憲章原則 VI 與 [round1-plan-brief.md](../../reference/round1-plan-brief.md) 鎖定，不在此重新評估；本文件處理的是「在既定技術棧下怎麼做」。

---

## R-01: 前端專案結構與路由

**Decision**: Next.js 15 App Router，TypeScript strict 模式。頁面依路由拆分（`/login`、`/onboarding`、`/(app)/dashboard`、`/(app)/trends`、`/(app)/profile`、`/(app)/capture`），共用外框（底部導覽列、主題）放在 route group layout。狀態管理不引入 Redux／Zustand 等全域狀態庫，改以 TanStack Query 管理伺服器狀態 + React 內建狀態管理本地 UI 狀態。

**Rationale**: 本輪的狀態幾乎全是「伺服器資料的快取與失效」（儀表板、紀錄清單、趨勢），這正是 TanStack Query 的問題領域；儲存紀錄後儀表板要即時更新（FR-041）用 query invalidation 一行解決，不需要自己寫同步邏輯。真正的本地狀態只有「辨識結果確認畫面的份量調整」，屬單一畫面內的短命狀態，用 `useState`／`useReducer` 即可。

**Alternatives considered**:

- Pages Router：與現行 Next.js 慣例背離，且 layout 巢狀需自行處理。
- 全域狀態庫（Zustand／Redux）：本輪沒有跨頁面共享的複雜客戶端狀態，引入後主要用途會退化成「快取伺服器資料」，與 TanStack Query 職責重疊。
- 照抄 prototype 的單頁 tab 切換 + 全域函式：brief 明確要求不照抄，且無法對應真實的 loading／錯誤狀態需求。

---

## R-02: LIFF 環境判斷與登入分流

**Decision**: 建立單一環境能力模組 `src/lib/liff/environment.ts`，對外只暴露 `getRuntimeEnv()`（回傳 `'liff' | 'web'`）與經過包裝的能力函式。判斷流程：

1. 嘗試 `liff.init({ liffId })`，成功後以 `liff.isInClient()` 判定是否在 LINE App 內建瀏覽器中。
2. `liff.init()` 失敗、逾時、或未設定 LIFF ID → 一律降級為 `'web'`，不拋出錯誤中斷頁面。
3. 判定結果快取於 React Context，全應用只判斷一次。

登入分流：`'liff'` → 取 `liff.getIDToken()` 送後端；`'web'` → 導向 LINE 網頁版 OAuth 授權端點，回呼後以 authorization code 送後端。所有 LIFF 專屬能力（`liff.closeWindow()`、`liff.getProfile()` 等）一律經由包裝函式呼叫，包裝函式在 `'web'` 環境回傳降級行為而非拋錯。

**Rationale**: 憲章原則 II 要求「不可假設一定執行於 LIFF context」，且明確禁止把 LIFF 判斷散落在各元件內。把判斷與能力包裝收斂成單一模組，讓「非 LIFF 環境誤呼叫 LIFF 專屬功能」在型別層面就不容易發生——元件拿不到原始 `liff` 物件。`liff.init()` 失敗即降級（而非重試或報錯）是關鍵設計：一般瀏覽器開啟時 `init` 本來就可能失敗，這是正常路徑不是異常路徑。

**Alternatives considered**:

- 以 User-Agent 判斷是否為 LINE 內建瀏覽器：UA 字串不穩定，LINE 改版即失效。
- 以建置期環境變數區分兩個部署版本：違反「同一前端同時支援兩種環境」的需求，且 Rich Menu 分流方式未定（本輪不決定，見 OQ-6），綁死部署會限制後續選項。
- 在每個元件內各自呼叫 `liff.isInClient()`：憲章明文禁止判斷邏輯散落。

---

## R-03: 後端 LINE 憑證驗證的單一路徑

**Decision**: 兩個入口各有一支專屬端點負責「取得可驗證的憑證」，但兩者都收斂到同一個核心函式 `verify_line_identity() -> LineIdentity`：

- `POST /api/v1/auth/line/liff`：接收 LIFF 取得的 ID Token → 以 LINE 的 ID Token 驗證端點驗證 → 取得 `sub`（LINE user id）、`name`、`picture`。
- `POST /api/v1/auth/line/callback`：接收網頁 OAuth 回呼的 authorization code → 以 channel id/secret 換取 token → 取得同一組 ID Token → **交給同一個 `verify_line_identity()`**。

核心函式之後的所有流程（建立或查詢 user、發本站 session、判斷是否需要引導填寫個人資訊）完全共用，`LineIdentity` 資料結構不帶任何「來源入口」欄位。

**Rationale**: 憲章原則 I 要求「後端驗證邏輯共用一套，不因入口不同分岔」。兩個入口的差異本質上只在「怎麼拿到 ID Token」——OAuth 多一次 code 換 token 的步驟。把差異侷限在端點層的前幾行，之後全部共用，是最貼近該原則的結構。刻意讓 `LineIdentity` 不帶入口資訊，可從型別上杜絕下游寫出 `if entry == 'liff'` 的分支。

**Alternatives considered**:

- 單一端點接受 `{type: 'liff'|'web', credential: ...}`：看似「一支 API」，但驗證邏輯內部反而出現分支，且 OpenAPI 契約會變成聯集型別，對前端型別安全不利。
- 前端自行換 token 後統一送 ID Token：需在前端持有 channel secret，安全上不可接受。

---

## R-04: 會話機制

**Decision**: 後端驗證通過後簽發自家的 access token（JWT，HS256，`sub` = 內部 user UUID，效期 7 天），前端存於 `localStorage` 並以 `Authorization: Bearer` 附帶。不使用 LINE 的 access token 作為本站憑證，不建 session 資料表。token 失效時後端回 401 + `code: "UNAUTHORIZED"`，前端攔截後導回登入並記住原本目標路徑（FR-008）。

**Rationale**: 四個客戶端（含未來 Flutter）共用同一後端（憲章原則 III），Bearer token 是唯一在 LIFF WebView、一般瀏覽器與原生 App 三種環境都行為一致的方案——Cookie 在 WebView 與跨站情境下行為不可預期。無狀態 JWT 在 25 人規模下不需要撤銷機制，省掉 session 表。效期 7 天是體驗與風險的折衷：LINE Mini App 的使用情境是高頻短時操作，過短會讓使用者頻繁重新授權。

**Alternatives considered**:

- HttpOnly Cookie + CSRF token：安全性較佳，但 LIFF WebView 與未來 Flutter 端的 Cookie 行為需個別處理，違反「不因入口分岔」的精神。
- 直接把 LINE access token 當本站憑證：每次請求都要向 LINE 驗證，增加外部相依與延遲；且無法承載本站的 role 等資訊。
- Access token + refresh token：本輪規模不需要，徒增複雜度。可於未來安全需求提高時再加，不影響現有契約。

---

## R-05: 樣式系統與深色模式

**Decision**: Tailwind CSS，深色模式採 `class` 策略（`darkMode: 'class'`），主題偏好存於 `localStorage` 並在文件載入前以 inline script 套用 `dark` class 以避免閃爍。prototype 的色彩、圓角、陰影、字重等視覺語彙抽成 Tailwind theme 設定（品牌色 `brand`、圓角尺度、陰影階層），元件依 Next.js 慣例重新拆分。

**Rationale**: prototype 本身就以 Tailwind 撰寫且使用 `dark` class 切換（brief 指定對照），沿用同一套設定可讓視覺一致性靠設定檔保證，而非靠人工比對。把色階與圓角抽成 theme token 而不是散落在 class 字串中，是「參考風格但不照抄結構」的具體做法。

**Alternatives considered**:

- CSS Modules／styled-components：需人工重建 prototype 的視覺語彙，偏差風險高。
- `darkMode: 'media'`：無法提供 prototype 已有的手動切換開關（設定頁的深色模式 toggle）。

---

## R-06: 趨勢圖表函式庫

**Decision**: Recharts。

**Rationale**: 宣告式 React 元件 API，與 App Router 的元件模型相容度高；SVG 輸出在圖表上有標註與無資料空狀態時較易處理（FR-054、FR-055）；套件體積在僅需折線／柱狀兩種圖表的情境下可接受。

**Alternatives considered**:

- Chart.js + react-chartjs-2：prototype 使用 Chart.js，視覺移植最直接，但其 canvas + imperative 更新模型需要額外的 ref 與生命週期管理，且切換指標／區間時的重繪需手動處理。視覺樣式可由 Recharts 設定重現，故不足以構成選用理由。
- 自行以 SVG 繪製：省下相依，但要自行處理座標軸、tooltip、響應式寬度，工作量與缺陷風險不划算。

---

## R-07: AI 辨識服務串接方式與非同步遷移評估

**Decision**: 本輪以**同步 HTTP 呼叫**實作：前端 `POST /api/v1/recognitions`（multipart 照片）→ 後端存檔並建立 `recognition_jobs` 紀錄 → 以 `httpx.AsyncClient` 呼叫同機辨識服務並等待 → 回寫結果 → 於同一個 HTTP 回應中回傳完整結果。逾時暫定 30 秒。

**關鍵設計：即使同步，API 也採「資源導向」而非「函式導向」形狀**——回應永遠是一個 recognition 資源：

```jsonc
{
  "id": "rec_01J...",
  "status": "completed",        // 目前只會是 completed / failed
  "items": [ ... ],
  "message": null
}
```

並同時提供 `GET /api/v1/recognitions/{id}` 讀取同一資源。前端一律經由 `useRecognition()` hook 消費，該 hook 內部以 `status` 驅動畫面（`processing` → Loading、`completed` → 結果頁、`failed` → 錯誤頁），**目前 `processing` 分支雖然不會被觸發，但畫面與狀態機先寫好**。

**非同步遷移影響評估**（brief 要求記錄）：

| 遷移後的變化 | 影響範圍 | 是否需改契約 |
|---|---|---|
| `POST /recognitions` 改回 `202` + `status: "processing"` | 後端端點內部 | 否（`status` 已是既有欄位，僅新增可能值） |
| 前端改為輪詢 `GET /recognitions/{id}` | `useRecognition()` hook 內部 | 否 |
| 結果畫面、Loading 畫面、錯誤畫面 | 無 | 否（狀態機已預留） |
| 逾時語意由「HTTP 逾時」改為「輪詢超過上限」 | hook 內部 + 後端 job 狀態 | 否 |
| 若改用 WebSocket／SSE 推送 | 新增傳輸層，`GET` 端點保留為 fallback | 新增，不破壞既有 |

結論：遷移成本集中在**後端一支端點的回應時機**與**前端一個 hook 的取得方式**，畫面層、資料模型（`recognition_jobs` 已有 `status`、`completed_at`、`error_code`）與 API 契約皆不需破壞性變更。這是把同步實作限制在「不外洩到契約形狀」的直接效果。

**⚠️ 此為待確認假設（OQ-1）**：實際呼叫方式與回應時間未定。若實測 p95 超過約 10 秒，同步等待會讓 HTTP 連線長時間佔用並惡化使用者感受，屆時應執行上述遷移。

**2026-08-04 更新**：R-16 確認辨識服務為第三方代管雲端服務（非同機部署），本節「同機低延遲」的隱含前提已不成立——p95 實測必須涵蓋公網往返延遲，30 秒逾時門檻的合理性需重新以外部服務的實測回應時間校準（OQ-4 隨之延續，不可視為已解決）。上述非同步遷移的契約影響評估結論不變。

**Alternatives considered**:

- 直接實作非同步輪詢：在回應時間未知的前提下，先付出輪詢的複雜度（job 狀態管理、輪詢節流、前端重試）卻不確定是否需要，違反憲章「Start simple」與 brief 的指示。
- 同步呼叫且 API 直接回傳 `items` 陣列（函式導向）：實作最短，但把「一次辨識是一個有生命週期的資源」這件事從契約中抹除，未來改非同步必然是破壞性變更——正是 brief 要求避免的「寫死成無法更改的架構決定」。
- 背景任務佇列（Celery／RQ）：同機部署、25 人規模下引入訊息佇列與 worker 程序，維運成本遠超收益。

---

## R-08: 錯誤分類與重試策略

**Decision**: 建立統一錯誤信封 `{"error": {"code": "...", "message": "...", "retryable": bool}}`，並定義以下辨識相關情境的處理：

| 情境 | 後端行為 | HTTP | code | 前端呈現 |
|---|---|---|---|---|
| 未偵測到食物（`items: []`） | 視為**成功**的辨識結果，原樣保留 `message` | 200 | — | 引導畫面：顯示服務訊息 +「重新拍攝」「返回」 |
| 辨識服務逾時（>30s） | job 標記 `failed`，`error_code=TIMEOUT` | 504 | `RECOGNITION_TIMEOUT` | 逾時說明 +「重試」（不需重選照片） |
| 辨識服務 5xx／連線失敗 | job 標記 `failed` | 503 | `RECOGNITION_UNAVAILABLE` | 服務忙碌說明 +「重試」，連續 3 次失敗後另外顯示「返回」 |
| 回應無法解析 | job 標記 `failed` | 502 | `RECOGNITION_BAD_RESPONSE` | 同上（技術細節不外露給使用者） |
| 照片格式不支援 | 上傳階段即拒絕 | 415 | `UNSUPPORTED_MEDIA_TYPE` | 提示可用格式，要求重新選擇 |
| 照片過大（>10MB） | 上傳階段即拒絕 | 413 | `PAYLOAD_TOO_LARGE` | 提示大小上限 |

**重試不需重新上傳照片**（FR-028）的實作方式：照片在第一次請求時即存檔並建立 `recognition_jobs` 紀錄，重試改呼叫 `POST /api/v1/recognitions/{id}/retry`，後端以既有照片重新呼叫辨識服務。前端只需保留 `recognition_id`。

後端對辨識服務**不做自動重試**——由使用者顯式觸發。理由：自動重試會讓已經在等待的使用者等更久（30s → 60s），且無法在等待期間給出「正在重試」以外的資訊；把重試決定權交給使用者，體驗與可預期性都較好。

**Rationale**: 「未偵測到食物」是**成功的辨識**而非錯誤，這個分類決定直接對應 FR-027——它走 200 而非錯誤路徑，前端才不會把它丟進通用錯誤處理而渲染出空清單。`retryable` 旗標讓前端不必維護 code → 是否可重試的對照表。

**Alternatives considered**:

- 把 `items: []` 視為 404／422 錯誤：語意錯誤（辨識確實成功執行了），且會誘導前端走通用錯誤畫面，失去 brief 要求的專屬引導畫面。
- 重試時重新上傳照片：使用者在行動網路下要再傳一次數 MB 檔案，體驗差且違反 FR-028。
- 後端自動重試 + 指數退避：見上述理由。

---

## R-09: 份量即時換算放在前端

**Decision**: 換算完全在前端執行，不呼叫後端。為此，`GET /recognitions` 系列端點回應的每個品項**必須包含每 100g 的原始營養值**（`per_100g`）與初始估計份量（`default_portion_grams`）：

```jsonc
{
  "food_reference_id": null,
  "name": "滷肉飯",
  "confidence": 0.93,
  "candidates": [],
  "default_portion_grams": 250,
  "per_100g": { "calories_kcal": 214, "protein_g": 8.0, "carbs_g": 24.0, "fat_g": 9.0 }
}
```

前端以 `value = per_100g[key] * grams / 100` 即時計算，顯示時四捨五入至整數（熱量）與一位小數（三大營養素）。**儲存時前端送出的是使用者確認後的份量與換算結果，後端以同一公式重新驗算**，差異超過容忍值即以後端計算值為準。

**Rationale**: brief 明確指示換算在前端做（公式簡單）。SC-003 要求 0.3 秒內更新，任何網路往返都無法穩定達成。後端重新驗算是必要的防線——前端送來的數值不可信，且能防止四捨五入誤差累積進歷史資料。回傳 `per_100g` 是這個決策的**必要條件**，也是本輪 API 契約中最容易被忽略而導致返工的一點。

**2026-08-04 更新**：本輪實際串接的外部辨識 API（R-16）**不提供** `per_100g`，只提供該估計份量下的絕對值（`calories`／`protein_g`／`carbs_g`／`fat_g`）與 `estimated_weight_g`。本決策的「必要條件」改由 `recognition_client.build_items()` 在 adapter 內以 `per_100g[key] = raw[key] / estimated_weight_g × 100` **反推**得出，繼續維持對前端與 `openapi.yaml` 一致的 `per_100g` 形狀——前端 `lib/nutrition.ts`／`PortionSlider` 不需任何改動。`candidates` 因新服務不提供 Top-K，一律回傳空陣列；`food_reference_id` 因不再依賴內部對照表換算，一律為 `null`。

**Alternatives considered**:

- 每次調整呼叫後端換算：達不到即時感，且在 25 人 × 每餐多次調整下產生大量無謂請求。
- 前端計算後端全盤信任：使用者可竄改任意營養數值；雖然本產品無金流風險，但會污染趨勢統計的可信度。
- 使用 debounce 後呼叫後端：仍有延遲，且複雜度高於直接前端計算。

---

## R-10: 照片上傳與儲存

**Decision**: 前端在上傳前於瀏覽器端壓縮（最長邊縮至 1280px、JPEG 品質 0.85），以 `multipart/form-data` 送出。後端存至同機檔案系統的資料卷（路徑 `{PHOTO_STORAGE_ROOT}/{user_id}/{yyyy}/{mm}/{uuid}.jpg`），資料庫只存相對路徑。存取一律經後端 `GET /api/v1/photos/{meal_record_id}` 並驗證擁有者，不開放靜態目錄直接對外。

**Rationale**: 辨識服務與主程式同機部署（brief 已確認），檔案系統是最短路徑——不需要物件儲存的網路往返與憑證管理。前端壓縮同時降低上傳時間（行動網路是主要使用情境）與辨識服務的解碼負擔。經後端代理存取而非開放靜態目錄，是 FR-044（使用者不得存取他人紀錄）在照片這一層的落實；直接開放目錄會讓路徑可猜測即可讀取。

**Alternatives considered**:

- 物件儲存（S3／MinIO）：本輪單機部署，引入額外服務不划算。惟路徑抽象為 `PhotoStorage` 介面，未來替換不需改動業務層。
- 照片以 BLOB 存進 PostgreSQL：資料庫體積膨脹、備份成本高，且無效能收益。
- 開放靜態目錄 + 難以猜測的檔名：安全性依賴檔名保密，不是存取控制。

**⚠️ 待確認（OQ-5）**：照片保留期限與使用者刪除紀錄時是否連帶刪除實體檔案，需依個資政策決定。本輪預設：刪除紀錄時同步刪除照片檔案。

---

## R-11: 資料表分離與營養值快照

**Decision**: 兩項獨立決策：

1. **通用食物營養對照表 `food_nutrition_references` 為完全獨立資料表**，不與任何店家／餐點資料表共用、不設外鍵關聯、不以 type 欄位混存。第二輪的店家餐點資料將是另一組資料表，兩者間唯一允許的關係是「無」。
2. **`meal_items` 儲存營養值快照**：寫入紀錄時把當下的 `per_100g` 數值一併寫入品項列，`food_reference_id` 僅作為來源追溯（可為 NULL，代表使用者自行輸入），且設為 `ON DELETE SET NULL`。

**Rationale**: 第 1 點是憲章原則 V 的直接要求，brief 亦重申。第 2 點解決一個實際問題：若歷史紀錄透過外鍵即時查詢營養值，日後修正對照表的數值會**追溯改變使用者的歷史攝取紀錄與趨勢圖**——這既違反使用者直覺，也讓 FR-016（重算目標不影響歷史紀錄）的精神在另一條路徑上被繞過。快照是紀錄型系統的標準做法。

**Alternatives considered**:

- 品項只存 `food_reference_id`，營養值即時 join：資料較「正規化」，但如上所述會讓歷史資料失去不可變性。
- 快照存整份 reference 的 JSON：欄位固定且少，攤平為具名欄位可查詢性更好。

**2026-08-04 更新**：外部辨識 API（R-16）串接後，來自辨識流程的 `meal_items.food_reference_id` 一律為 `NULL`——新服務的營養值已由其自身提供，不再透過 `model_label` 查 `food_nutrition_references` 換算，兩者之間不再有辨識路徑上的關聯。`food_reference_id` 目前僅在使用者經由 `GET /foods/search`（FR-037 手動修正）選定品項時才會被寫入。快照機制（本節決策 2）不受影響，`food_nutrition_references` 的獨立資料表地位（本節決策 1、憲章原則 V）亦不受影響。

---

## R-12: 時區與日期歸屬

**Decision**: 所有時間戳以 `TIMESTAMPTZ` 存 UTC；`meal_records.record_date` 另存一個 `DATE` 欄位，由後端依**固定時區 `Asia/Taipei`** 換算後寫入。儀表板與趨勢查詢一律以 `record_date` 為準，不在查詢時做時區換算。

**Rationale**: FR-040 要求以使用者所在時區歸屬日期。本輪目標使用者為台灣在地飲食族群（產品願景明定），固定 `Asia/Taipei` 可讓「今天吃了多少」在跨午夜時符合直覺，且避免使用者跨時區旅行時歷史紀錄的歸屬日期跳動。把歸屬日期物化成欄位而非查詢時計算，讓日期彙總可直接用索引，也讓「這筆屬於哪一天」成為可稽核的既定事實。

**Alternatives considered**:

- 依裝置回報時區動態換算：使用者出國時，同一批歷史紀錄的歸屬日會隨當下時區改變，趨勢圖會前後不一致。
- 查詢時以 `AT TIME ZONE` 即時換算：每次查詢都要換算，且無法對 `date_trunc` 結果建索引。
- 未來若需支援跨時區使用者，改法是在 `health_profiles` 加 `timezone` 欄位、寫入時採用該值——現有結構不需破壞性變更。

---

## R-13: 每日目標計算公式

**Decision**:

- **BMR**：Mifflin-St Jeor —— `10 × 體重kg + 6.25 × 身高cm − 5 × 年齡 + (男 +5 / 女 −161)`
- **TDEE**：`BMR × 活動係數`，低 = 1.2、中 = 1.45、高 = 1.75（與 prototype 一致）
- **蛋白質**：`體重kg × 1.8` 公克
- **脂肪**：`TDEE × 0.25 ÷ 9` 公克
- **碳水**：`(TDEE − 蛋白質g×4 − 脂肪g×9) ÷ 4` 公克

計算集中於後端 `services/targets.py` 單一函式，前端只顯示後端算好的結果。

**Rationale**: Mifflin-St Jeor 是目前公認誤差較低的 BMR 估算式，且 prototype 已採用，沿用可保持與既有設計一致。計算放在後端而非前端，是因為 TDEE 會被寫入資料表並影響儀表板與趨勢的達成率計算——同一份數值若前後端各算一次，浮點與四捨五入差異會造成畫面與資料庫不一致。

**Alternatives considered**:

- Harris-Benedict 公式：較舊，對現代體組成的誤差較大。
- 讓使用者自訂目標熱量：spec 的 Assumptions 已明確排除於本輪。
- 前端計算後送出：使用者可竄改目標值，且違反單一真實來源。

---

## R-14: 權限層的前瞻設計

**Decision**: 本輪**不實作管理員功能與後台端點**，但預先建立兩項結構：

1. `users` 資料表含 `role` 欄位（`user` / `admin`，預設 `user`），本輪所有使用者皆為 `user`。
2. FastAPI 依賴注入分兩層：`get_current_user()`（本輪全部端點使用）與 `require_admin()`（本輪不掛載於任何端點，僅建立並附單元測試）。

所有資料查詢一律以 `WHERE user_id = current_user.id` 收斂，不存在「查全部再過濾」的路徑。

**Rationale**: 憲章原則 IV 要求建立僅管理員可通過的權限檢查層，且明訂本輪的後端設計不得妨礙後續加入。先放 `role` 欄位與依賴注入骨架的成本接近零，但可避免第二輪為了加角色而做資料遷移與大範圍端點改寫。同時這也讓「一般使用者存取管理端 API 被拒絕」這條憲章必測情境在本輪就能寫出測試（測 `require_admin()` 本身），而不是等到有端點才補。

**Alternatives considered**:

- 完全不碰角色，第二輪再加：屆時需對既有使用者資料做遷移、重新設計所有端點的授權層，且憲章要求的必測情境在本輪無法成立。
- 本輪就實作完整 RBAC（權限表、角色表、權限指派）：明確超出本輪範圍，違反 brief 的排除清單與憲章「不為單一功能引入平行機制」。

---

## R-15: 測試策略

**Decision**:

| 層級 | 工具 | 涵蓋重點 |
|---|---|---|
| 後端單元 | pytest | 目標計算公式、營養換算與驗算、錯誤分類映射、`require_admin()` 拒絕行為 |
| 後端整合 | pytest + httpx `ASGITransport` + testcontainers PostgreSQL | 端點層授權、資料隔離（跨使用者存取回 404/403）、辨識流程各錯誤分支 |
| 辨識服務契約 | pytest + 可切換模式的 stub 服務 | 正常回應、空 items、逾時、5xx、格式錯誤五種模式 |
| 前端單元 | Vitest + React Testing Library | 份量即時換算、環境判斷模組降級行為、錯誤畫面分支 |
| 端對端 | Playwright | 兩種入口各走一次完整 User Flow |

憲章要求的兩類必測情境明確對應：「一般使用者存取管理端 API 被拒絕」→ 後端單元 + 整合；「非 LIFF 環境可完成登入流程」→ 前端單元（`liff.init()` 失敗即降級）+ Playwright（一般瀏覽器走 OAuth）。

**Rationale**: 可切換模式的 stub 讓錯誤處理路徑不需依賴外部服務即可完整驗證，且不消耗真實 API 的金鑰額度——這正是本輪需求密度最高、最容易漏測的區塊。testcontainers 讓整合測試跑在真 PostgreSQL 上，避免 SQLite 與 PostgreSQL 的行為差異（`TIMESTAMPTZ`、`NUMERIC` 精度）在上線後才暴露。

**2026-08-04 更新**：辨識服務的真實介面已於 R-16 確認（OQ-3 關閉），stub 的模式定義已對齊真實契約格式（見 [contracts/recognition-service.md](./contracts/recognition-service.md)「本機開發用 Stub」）。

**Alternatives considered**:

- 整合測試用 SQLite in-memory：快，但本設計依賴 `TIMESTAMPTZ`、`NUMERIC`、`ON DELETE SET NULL` 等行為，差異風險高。
- 只做端對端測試：辨識的錯誤分支（逾時、5xx）難以在 E2E 穩定重現。
- 對辨識服務做真實呼叫測試：服務尚未就緒，且會讓測試依賴外部狀態。

---

## R-16: 辨識服務改為外部代管 API（台灣小吃辨識 API）串接

**Decision**: 辨識服務由「假定的同機內部服務」正式改為串接第三方代管的雲端 API（`https://taiwanese-food-api-528488788338.asia-east1.run.app/api/detect`，`X-API-Key` 認證）。完整契約見 [contracts/recognition-service.md](./contracts/recognition-service.md)。本節記錄該契約帶來的三項關鍵技術決策：

**1. 反推 `per_100g`，收斂於 adapter 層**：新服務回傳的是該估計份量下的絕對營養值 + `estimated_weight_g`，不是 `per_100g`。決定由 `recognition_client.build_items()` 以 `per_100g[key] = raw[key] / estimated_weight_g × 100` 反推，維持對前端與 `openapi.yaml` 既有的 `per_100g` 契約形狀不變（詳見 R-09 的 2026-08-04 更新）。

**理由**：`services/recognition_client.py` 是 OQ-3 當初唯一設計的變更隔離點（見 spec 的原始契約文件），把契約差異全部吸收在這一層，前端 `PortionSlider`／`lib/nutrition.ts`／`useRecognition.ts` 與 `contracts/openapi.yaml` 完全不需改動——這正是當初預留該隔離層的目的得到驗證的時刻。

**已否決的替代方案**：讓前端改為消費 `estimated_weight_g` + 絕對值、自行反推單位值。理由：會同時觸及 `PortionSlider` 元件與 `lib/nutrition.ts` 的計算邏輯，且需要前後端各自實作一次等價公式（重新驗算仍在後端），徒增不一致風險，且違背「契約差異只改一個檔案」的既有設計意圖。

**2. `food_reference_id` 與 `food_nutrition_references` 解耦**：辨識路徑產生的品項一律 `food_reference_id = null`（見 R-11 的 2026-08-04 更新）。`food_nutrition_references` 資料表**不廢除**，改為僅供 `GET /foods/search`（FR-037 手動修正食物名稱）使用，與辨識流程本身脫鉤。憲章原則 V（通用食物對照表獨立、不與店家資料共用）不受影響——這條原則本就未預設對照表的唯一用途是「辨識查表」。

**3. 金鑰管理**：`X-API-Key` 存於後端環境變數（暫定 `RECOGNITION_API_KEY`），比照 `LINE_CHANNEL_SECRET` 的既有管理方式（`.env` 本機、正式環境的 secret 管理機制，不進版本控制）。錯誤處理時（`RecognitionServiceError`）不得將金鑰或原始 header 內容寫入對外錯誤訊息或一般 log；`401` 一律對外呈現為 `RECOGNITION_UNAVAILABLE`（服務暫時不可用），不區分是金鑰問題還是服務端問題，避免向使用者或潛在攻擊者洩漏認證細節。金鑰輪替本輪不建立自動化機制（單一固定金鑰、25 人規模），輪替時需同步更新環境變數並重啟服務，記錄於部署手冊（quickstart.md）。

**連帶影響**：

- **R-07（同步呼叫）**：「同機低延遲」前提不再成立，OQ-1／OQ-4 的實測需涵蓋公網延遲，見 R-07 的 2026-08-04 更新。
- **R-08（錯誤分類）**：情境對照表新增「`401` 認證失敗 → `RECOGNITION_UNAVAILABLE`」一列，見 [contracts/recognition-service.md](./contracts/recognition-service.md) 情境對照表；其餘錯誤分類（逾時／5xx／連線失敗／解析失敗）語意不變。
- **R-09（份量即時換算）**：per_100g 反推，見上方決策 1。
- **R-11（資料表分離與快照）**：`food_reference_id` 解耦，見上方決策 2；`meal_items` 快照機制本身不受影響。

**Alternatives considered**:

- 維持假定契約、待模型端自建同機服務就緒後再串接：會讓辨識功能無限期停留在 stub 階段，且已取得可用的真實 API，沒有理由延後驗證。
- 前端直接呼叫外部辨識 API（略過後端）：違反憲章原則 III（單一後端）與原則 I 的驗證收斂精神，且會讓 `X-API-Key` 暴露於客戶端。

---

## Open Questions（帶入 plan.md 追蹤）

| ID | 問題 | 現行假設 | 影響 | 需在何時決定 |
|---|---|---|---|---|
| OQ-1 | 辨識服務為同步或非同步？回應時間 p95 為何？ | 同步，逾時 30s；p95 待實測（**須涵蓋外部服務公網延遲，見 R-16**） | 見 R-07 遷移評估；若 p95 > 10s 應改非同步 | 實作辨識串接前 |
| OQ-2 | 通用食物營養對照表的資料來源與涵蓋範圍 | 本輪自建，供 FR-037 手動搜尋使用（**不再是辨識結果換算的必經路徑，見 R-16**） | 直接決定本輪工作量 | 資料表建立前 |
| ~~OQ-3~~ | ~~辨識服務的實際 HTTP 介面~~ | **已確認關閉（2026-08-04）**：見 [contracts/recognition-service.md](./contracts/recognition-service.md)、R-16 | — | 已解決 |
| OQ-4 | 逾時門檻 30 秒是否合適 | 30s，**需依外部服務實測回應時間重新校準（見 R-07 更新）** | 過短會誤判正常回應為逾時 | 取得 OQ-1 實測後 |
| OQ-5 | 照片保留期限與刪除政策 | 刪除紀錄時同步刪除照片 | 個資合規 | 上線前 |
| OQ-6 | LINE 官方帳號 Rich Menu 分流方式（同一前端不同路由 vs 兩組 LIFF） | 本輪不決定 | 不影響本輪實作 | 第二輪（推薦餐廳）plan |
| OQ-7 | 個人健康檔案是否納入「性別」欄位 | 納入（BMR 公式所需） | 不納入則需改用不需性別的估算式，精確度下降 | 資料表建立前 |
| OQ-8 | 年齡以「歲數」或「出生日期」儲存 | 歲數（與 prototype 一致） | 歲數會隨時間失準，需使用者自行更新 | 資料表建立前 |
| OQ-9 | `RECOGNITION_API_KEY` 的正式環境輪替流程 | 本輪僅手動輪替並更新環境變數，無自動化機制 | 金鑰外洩時的應變速度 | 上線前 |
