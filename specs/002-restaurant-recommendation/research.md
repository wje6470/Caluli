# Research: 推薦餐廳（第二輪）

**Date**: 2026-08-04 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

技術規劃補充依據：[reference/round2-plan-brief.md](../../reference/round2-plan-brief.md)
資料表共用契約：[reference/shared-schema-store-menu.md](../../reference/shared-schema-store-menu.md)

本輪不引入任何新技術選型（brief 明訂）。以下決策全部落在「既有技術棧內怎麼做」的層次。

---

## R-01：距離計算放在應用層，不放 SQL、不引入 PostGIS

**Decision**：在 Python 應用層以 Haversine 公式計算距離。後端一次取出所有具備有效座標的店家，於服務層計算距離、過濾 5 公里、排序、取前 10。

**Rationale**：

brief 已排除 PostGIS，剩下的選擇是「應用層迴圈」與「SQL 內嵌 Haversine 公式」。取捨如下：

| 面向 | 應用層計算（採用） | SQL 層計算（否決） |
|---|---|---|
| 單元測試 | 純函式，`haversine_km()` 無需資料庫即可測邊界值與已知距離 | 公式在 SQL 字串或 SQLAlchemy `func` 拼裝中，驗證必須起資料庫（testcontainers） |
| 公式可讀性 | 一個具名函式，數學式與註解同處 | 三角函式以 `sa.func.acos(sa.func.sin(...))` 層層包裝，易寫錯且不易看出錯在哪 |
| 資料傳輸量 | 取回全表（本輪數十筆，可忽略） | 資料庫端 `LIMIT 10`，傳輸量固定 |
| 排序與過濾一致性 | 半徑過濾、排序、取前 10 都在同一段程式，順序明確 | 需在 SQL 中同時處理 NULL 座標、半徑、排序，條件散落 |
| 未來成長 | 店家數上千時需改寫 | 天然可擴展 |

憲章「開發流程與品質門檻」要求涉及變更具備對應測試，而距離排序的正確性正是本輪最核心的可測邏輯（SC-002）。可在無資料庫環境下驗證公式，是本輪選擇應用層的決定性理由。資料傳輸量的劣勢在 brief 明示的「店家數量不大」前提下不成立。

**成長觸發點（先寫下來，避免日後憑感覺改架構）**：店家數達約 1,000 筆前，本作法的成本可忽略。超過後的升級順序為 (1) 先在 SQL 加經緯度 bounding box 粗篩（`WHERE latitude BETWEEN ? AND ?`）再於應用層精算，(2) 仍不足才評估 PostGIS。本輪不實作 (1)，因為它會讓半徑邏輯同時存在於 SQL 與 Python 兩處。

**Alternatives considered**：PostGIS `ST_DWithin` + GiST 索引——正確且高效，但 brief 明確排除，且 Supabase 啟用擴充套件會成為第三輪分支的部署前提，跨分支風險大於效益。

---

## R-02：第一輪**沒有**可重用的權限請求元件，本輪必須自建

**Decision**：新建 `frontend/src/lib/geo/location.ts` 封裝 `navigator.geolocation`，回傳可辨識聯集（discriminated union）；並新建 `components/ui/PermissionNotice.tsx` 作為**呈現層**共用元件。

**Rationale**：

brief 要求「比照第一輪相機權限的既有實作模式」。實際查核第一輪程式碼的結果是——**該模式不存在於程式碼中**：

- [frontend/src/app/(app)/capture/page.tsx](../../frontend/src/app/(app)/capture/page.tsx) 取得相機的方式是 `<input type="file" accept="image/*" capture="environment">`。權限完全由作業系統的檔案選擇器處理，前端沒有呼叫任何 Permissions API。
- 因此第一輪**無法偵測**權限是否被拒——它的「被拒處理」是一段恆常顯示的靜態提示文字加上「從相簿選取」按鈕（`SourcePicker` 底部），而非依權限狀態分支。
- `frontend/src/lib/capture/` 下只有 `draft.ts` 與 `image.ts`，沒有權限相關模組。

所以「比照第一輪」只能在 **UX 原則層級**成立，本輪據此沿用其三項原則：

1. **不預先請求**——使用者主動進入該功能時才請求，而非進站即要權限。
2. **被拒不阻斷**——一律提供替代路徑（第一輪為相簿，本輪為全部店家清單）。
3. **明示如何恢復**——畫面上說明如何重新開啟權限。

而定位與相機在**取得機制**上有本質差異，這個差異正是本輪能滿足 FR-007 的原因：`navigator.geolocation` 的錯誤物件帶 `code`，可精確區分規格要求的兩類情境，而 file input 完全沒有這個訊號。

```
GeolocationPositionError.code
  1 PERMISSION_DENIED    → 'denied'       → FR-008 拒絕授權畫面（指向權限設定）
  2 POSITION_UNAVAILABLE → 'unavailable'  → FR-009 定位失敗畫面（指向裝置設定，可重試）
  3 TIMEOUT              → 'unavailable'  → 同上，逾時（FR-010）
```

**共用可行性評估（brief 要求評估）**：

| 層 | 可否共用 | 結論 |
|---|---|---|
| 取得機制 | ❌ | file input 與 geolocation API 無共同抽象，強行統一只會產出一個空洞的介面 |
| 狀態模型 | ⚠️ 部分 | 第一輪無狀態可言（偵測不到拒絕），無從共用 |
| 呈現層（圖示＋標題＋說明＋主要動作＋次要動作） | ✅ | 兩者的「被拒畫面」視覺結構相同，可抽為 `PermissionNotice` |

**本輪作法**：建立 `PermissionNotice` 呈現元件並供推薦餐廳使用。第一輪 `SourcePicker` 底部提示改用此元件屬**可選後續改善**，不列入本輪範圍——第一輪流程已驗收，為了形式一致而改動已上線程式碼，風險大於收益。

**Alternatives considered**：用 Permissions API (`navigator.permissions.query({name:'geolocation'})`) 預先查詢權限狀態以決定是否顯示請求前的說明畫面。否決：iOS Safari 對 geolocation 的支援不一致，且會多一層與實際請求結果可能不同步的狀態。直接呼叫 `getCurrentPosition` 並依錯誤碼分支，狀態來源單一。

---

## R-03：LIFF-only 落實於前端入口與路由守衛，後端不分岔

**Decision**：前端雙重把關——`BottomNav` 的「找餐廳」分頁僅在 `isInLiff()` 為真時渲染；`/restaurants` 路由本身也自行檢查環境，非 LIFF 直接進入（例如手打網址）時顯示「此功能僅於 LINE 內提供」並提供返回。後端 `GET /stores*` 端點不檢查來源入口。

**Rationale**：憲章原則 III 與「架構約束」要求後端 API 契約對四端一致、不得因客戶端不同而提供不同語意的端點。若後端擋非 LIFF 來源，等同建立入口專屬端點，直接牴觸。且「僅 LIFF 提供」在 spec 中是**功能範圍**的界定（哪個入口做這個畫面），不是安全邊界——店家與餐點是所有登入使用者皆可讀的非敏感資料，沒有機密性理由需要後端強制。

此判斷已記於 [spec.md](./spec.md) 的 Assumptions；若後續確認需要後端強制，屬新增的安全需求。

**Alternatives considered**：後端以 `X-Client-Entry` header 或 token claim 區分入口並拒絕非 LIFF——否決（牴觸憲章，且 header 可偽造，提供的是安全假象）。

**實作注意**：`isInLiff()` 是同步函式，需 `initRuntimeEnv()` 已完成才有意義（[environment.ts](../../frontend/src/lib/liff/environment.ts) 快取判定結果）。`(app)/layout.tsx` 目前沒有等待環境初始化，導覽列首次渲染時 `isInLiff()` 可能仍為 `null` 狀態。因此本輪在 `BottomNav` 使用「環境判定完成前不顯示該分頁」的保守策略——寧可晚一瞬間出現，不可在一般網頁短暫閃現（FR-002）。

---

## R-04：查詢管線的順序固定為「排除無效座標 → 算距離 → 半徑過濾 → 排序 → 取 10」

**Decision**：後端服務層以此固定順序處理，5 公里與 10 筆兩個常數集中於 `app/core/config.py`。

**Rationale**：順序寫死於單一函式可避免三個易錯點——(a) 先取 10 再過濾半徑會得到少於 10 筆的錯誤結果（FR-020 明文禁止以範圍外店家補足，但反過來先截斷也錯）；(b) NULL 座標若未先排除會在距離計算產生例外或被當作 (0,0) 而排到最前（FR-018）；(c) 排序前未完成過濾會讓 `LIMIT` 落在錯誤集合上。

常數集中的理由見 spec Assumptions：5 公里為暫定值，實地測試後可能調整，調整不應散落多處。

```python
NEARBY_RADIUS_KM = 5.0   # spec FR-020
NEARBY_LIMIT = 10        # spec FR-014
```

---

## R-05：空狀態的語意差異由 API 提供，不由前端猜

**Decision**：店家清單回應一律附帶 `total_store_count`（資料庫中的店家總數，不受半徑與筆數限制影響）。

**Rationale**：spec 要求三種空狀態各自可區分（FR-019、SC-004），但前端只看 `stores: []` 無法分辨「資料庫根本沒有店家」與「有店家但都在 5 公里外」——兩者的文案與可用操作完全不同（後者要提供「改看全部店家」，前者提供這個按鈕只會導向另一個空清單）。

讓前端額外呼叫一次不帶座標的查詢來推斷，等於用兩次往返換一個後端本來就知道的事實。因此由回應直接帶出：

| `stores` | `total_store_count` | 前端呈現 |
|---|---|---|
| 非空 | 任意 | 正常清單 |
| 空 | `> 0` | 「附近查無店家」＋「改看全部店家」（FR-019） |
| 空 | `0` | 「目前尚無店家資料」，不提供改看操作（US3-5） |

---

## R-06：單一 `/stores` 端點，以有無座標參數切換模式

**Decision**：`GET /stores`（全部模式）與 `GET /stores?lat=&lng=`（附近模式）為同一端點；回應帶 `mode` 欄位明示當前模式，`distance_m` 在全部模式下為 `null`。

**Rationale**：兩者是同一資源的兩種檢視，不是兩種資源。分成 `/stores` 與 `/stores/nearby` 會讓「附近查無 → 改看全部」變成跨端點切換，前端需維護兩組 query key 與兩種回應型別，而兩者的清單項目結構其實只差一個 `distance_m`。

`lat` 與 `lng` 必須同時提供或同時省略，只給其一視為 `VALIDATION_ERROR`（避免無聲地退回全部模式，讓前端誤以為使用者位置已納入計算）。

**Alternatives considered**：永遠回傳全部店家、由前端計算距離與排序——否決。座標比對邏輯會同時存在於前後端兩份實作（第一輪份量換算是刻意這麼做，因為那是為了免除 API 往返的即時互動，本輪沒有同等理由），且店家成長後傳輸量無上限。

---

## R-07：座標驗證在前後端各做一次，語意不同

**Decision**：後端以 Pydantic 驗證 `lat ∈ [-90, 90]`、`lng ∈ [-180, 180]`，違反回 `422 VALIDATION_ERROR`。前端在送出前先驗，違反則**不呼叫 API**，直接走「定位失敗」畫面。

**Rationale**：spec Edge Case 要求「取得的座標明顯不合理 → 視同定位失敗處理」。若前端把無效座標送給後端，使用者會看到通用 API 錯誤而非定位失敗的專屬畫面與重試按鈕——是不同的使用者體驗。後端的驗證則是防止異常輸入進入距離計算的必要防線，兩者目的不同，不是重複。

---

## R-08：餐點營養的 `0` 與 `NULL` 是兩種不同的有效狀態

**Decision**：`menu_items` 的四個營養欄位允許 NULL；API 原樣回傳 `null` 與 `0`，不做任何正規化；前端 `null` → 「無資料」，`0` → `0`。

**Rationale**：FR-025 要求雙向區分——缺值不得顯示為 0（會被讀成「不含該營養素」），數值 0 也不得顯示為「無資料」（會抹掉店家明確登錄的資訊）。要在呈現層區分兩者，資料層就必須能區分；NOT NULL + 預設 0 會使這個區分在寫入當下即永久喪失。

2026-08-04 第三輪交接說明確認了**「營養數值為 0 → 正常顯示為 0，非『無資料』」**，與本決策一致。最容易寫錯的是後端 Pydantic 或前端格式化函式用 `value or "無資料"` 之類的 falsy 判斷——`0` 是 falsy，會被誤判為缺值。必須以 `is None` / `=== null` 明確判斷，此點列入單元測試（R-11）。

**⚠️ 仍未定案**：交接說明確認了 0 的行為，但**未言明 NULL 是否允許寫入**。若第三輪將四個欄位設為 NOT NULL，「無資料」狀態將永不出現（呈現邏輯無害但成為死碼），FR-025 的前半段隨之落空。登記為 **OQ-2b** 待確認。本輪**不**因此增減欄位（brief 明訂）。

---

## R-09：測試資料以 seed script 提供，不放進 migration

**Decision**：`backend/app/scripts/seed_stores.py`，需手動執行；資料以模組內字面值定義，主鍵用 `uuid5` 由固定命名空間與店名推導。

**Rationale**：

- **不放 migration**：migration 會在每個環境自動執行，假店家將自動進入正式資料庫，而移除它們需要另一支 migration。第三輪的後台一旦寫入正式資料，正式與測試資料混在同一張表卻無欄位可區分（契約無 `is_test` 欄位，本輪也不得增加），清理成本高。seed script 需要有人主動執行，環境邊界清楚。
- **`uuid5` 決定性主鍵**：同一份 seed 重複執行為 upsert 而非重複插入，且測試可直接以已知 UUID 斷言，不需先查詢。
  **⚠️ 店名不唯一（2026-08-04 交接確認），因此 uuid5 不可只由名稱推導**。seed 內的推導鍵為 `f"{店名}|{地址}"`（店家）與 `f"{店家UUID}|{索引}|{餐點名}"`（餐點），並在 seed 資料中刻意放入一組同名不同址的連鎖分店以驗證 FR-016a。這是 seed 內部的識別方式，**不是**對資料表的唯一性假設——正式資料的識別一律靠 `id`。
- **識別為測試資料（FR-035）**：契約沒有可標記的欄位，故以**店名前綴 `[測試]`** 達成。前綴會顯示在畫面上，這是刻意的——測試環境一眼可辨，且正式資料寫入後兩者並存也不會被誤認。刪除時以 `name LIKE '[測試]%'` 即可精準清除。

**資料組成**（滿足 FR-034 與 quickstart 全部驗證情境）：以台北車站 `(25.0478, 121.5170)` 為參考點，5 公里內 12 家（涵蓋 >10 筆以驗證截斷）、5 公里外 2 家（淡水、基隆，驗證半徑排除與「改看全部店家」）、另 1 家座標留空（驗證 FR-018，此為後台允許的常態資料）、另一組**同名不同址的連鎖分店**（驗證 FR-016a：以 id 識別、以地址區分）。餐點方面：至少一家 8 筆以上餐點（驗證捲動）、一家 0 筆（驗證空狀態）、一筆四欄皆 NULL（驗證「無資料」）、**一筆數值確實為 0**（驗證 0 顯示為 0 而非「無資料」，R-08）、一組同店同名餐點（驗證不去重）。

---

## R-10：座標取得包成 TanStack Query，讓「返回不重取、重載才重取」自然成立

**Decision**：以 `useQuery({ queryKey: ['geolocation'], queryFn: requestCurrentLocation, staleTime: Infinity, gcTime: 5分鐘, retry: false })` 取得座標。

**Rationale**：spec 有兩條看似衝突的要求：

- FR-026／US2-4：從餐點頁返回時，清單維持原排序且**不得**重新請求定位權限。
- US1-7：重新載入或再次進入該頁時，**必須**以當下座標重新計算。

以 query cache 承載座標，兩者同時成立且不需額外狀態管理：頁面內導覽（Next.js client-side navigation）時 cache 仍在 → 命中，不觸發 `getCurrentPosition`；整頁重載時 cache 隨頁面銷毀 → 重新取得。若改用 `sessionStorage` 保存座標，重載後會沿用舊座標，直接違反 US1-7；若改用元件 state，返回時元件已卸載，會重新請求權限而違反 FR-026。

`retry: false` 是必要的：定位失敗要立刻呈現失敗畫面與**使用者主動**的重試按鈕（FR-009），自動重試會讓畫面卡在載入狀態且重複彈出權限提示。

前端逾時設 10 秒（`getCurrentPosition` 的 `timeout` 選項，spec Assumptions 暫定值），對應 FR-010。

---

## R-11：測試策略

**Decision**：

| 層 | 測試 | 覆蓋 |
|---|---|---|
| 後端單元 | `haversine_km()` 已知距離／同點為 0／跨經度換日線／極值座標 | R-01、SC-002 |
| 後端單元 | 查詢管線順序：NULL 座標排除、半徑邊界（恰 5.0 km）、超過 10 筆截斷、不足 10 筆不補 | FR-014、FR-018、FR-020 |
| 後端整合 | `GET /stores` 三種空狀態的 `total_store_count`、未登入 401、不存在店家 404 | FR-019、FR-027、R-05 |
| 後端整合 | **無任何寫入端點存在**（斷言 OpenAPI schema 中 `/stores*` 僅有 GET） | FR-029 |
| 後端整合 | 憲章原則 V：菜單查詢不觸及 `food_nutrition_references` | FR-030、FR-031 |
| 前端單元 | `location.ts` 三種錯誤碼各自映射到正確狀態 | FR-007 |
| 前端單元 | 距離格式化（公尺／公里切換） | FR-016 |
| 前端單元 | ★ 營養值 `null` → 「無資料」**且** `0` → `0`（防 falsy 誤判） | FR-025、R-08 |
| 前端單元 | 同名不同址的店家各自獨立呈現，清單 key 用 id | FR-016a |
| 前端 E2E | LIFF 模擬下：允許定位 → 清單 → 餐點 → 返回（不再請求權限） | US1、US2、FR-026 |
| 前端 E2E | 非 LIFF 環境看不到「找餐廳」入口 | FR-002、SC-006 |

憲章明列的兩類必測情境（管理端 API 拒絕、非 LIFF 可登入）於第一輪已建立，本輪不重複；但本輪新增的「非 LIFF 環境不呈現本模組」是同一原則的延伸，列入上表。

---

## Open Questions

**2026-08-04 第三輪執行清單給出了最終欄位定義，跨分支的 Open Question 全數結案。** 僅餘兩項與第三輪無關的本輪自身待辦。

### 已結案

| ID | 原問題 | 最終結論（第三輪定義） | 對本輪的影響 |
|---|---|---|---|
| ~~OQ-1~~ | 主鍵型別（UUID vs BIGSERIAL） | **UUID**，default `gen_random_uuid()` | 與本輪建議一致，無需修改 |
| ~~OQ-2b~~ | 四個營養欄位是否允許 NULL | **NULL**，CHECK `>= 0`；對方有測試斷言「NULL 不會被寫成 0」 | 與本輪建議一致。FR-025 的「無資料」分支確定會實際發生，非死碼 |
| ~~OQ-2（座標）~~ | 經緯度是否 nullable | **NULL**，並以 CHECK `(latitude IS NULL) = (longitude IS NULL)` 於 DB 層保證成對 | 保證比預期更強（原本只靠寫入端）。防禦性檢查仍保留 |
| ~~OQ-3~~ | `name`／`address` 的型別與 nullability | `name` VARCHAR(255) NOT NULL 且**不唯一**；`address` VARCHAR(500) **NOT NULL** | ⚠️ `address` 由原先假設的 nullable 改為 **NOT NULL**，見下方註記 |
| ~~OQ-4~~ | `menu_items` 缺時間戳 | **補上** `created_at`／`updated_at` | 僅 model 增列，本輪不讀取、不對外呈現。API 契約不變 |
| ~~OQ-5~~ | 店家刪除時餐點的行為 | **實刪除 + `ON DELETE CASCADE`**；無 `deleted_at`／`is_active` | 查詢**不得**加任何軟刪除過濾（FR-018a） |
| ~~OQ-6~~ | 由哪一方建表 | **第三輪建立**（他們負責寫入）。本輪已刪除自己的 migration | 見 [data-model.md](./data-model.md)「Migration 與 model 歸屬」 |

**`address` 改為 NOT NULL 的影響**：本輪的讀取端型別（`StoreOut.address: str | None`、
前端 `address: string | null`）**刻意維持可空**。理由是本輪不再擁有這張表的 schema，
保持寬容的讀取型別成本為零、行為不變（前端已有 `?? '地址未提供'` 的退路），
而一旦對方日後放寬約束也不需要跟著改。FR-016「地址必須顯示」因 NOT NULL 而更有保障。

### 本輪自身待辦（與第三輪無關）

| ID | 問題 | 現行值 | 需在何時決定 |
|---|---|---|---|
| OQ-7 | 5 公里半徑是否符合實際使用情境 | 5.0 km（使用者已於 specify 階段決定） | 實地測試後 |
| OQ-8 | 地址→座標的自動地理編碼 | 不做，座標由第三輪後台人工輸入（brief 明訂） | 第三輪或之後 |
