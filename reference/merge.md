一、backend/app/main.py

打開檔案,找到這兩處衝突,直接手動改成下面這樣(刪掉 <<<<<<<、=======、>>>>>>> 標記):

第一處(import)：

python
from app.api.v1 import (
    admin_menu_items,
    admin_session,
    admin_stores,
    analytics,
    auth,
    foods,
    meal_records,
    profile,
    recognitions,
    stores,
)

（把第二輪的 stores 加進 main 那份 import 清單裡，按字母順序排即可，不影響功能）

第二處(router 掛載)：

python
v1.include_router(recognitions.router)
v1.include_router(meal_records.router)
v1.include_router(analytics.router)
v1.include_router(foods.router)
v1.include_router(stores.router)  # 第二輪：推薦餐廳（唯讀查詢）

# --- 管理端（憲章原則 IV）---
# 與上方一般使用者端點分開掛載。權限檢查掛在各 admin router 的建構參數上
# （dependencies=[Depends(require_admin)]），不在此處逐一補掛——那樣會在
# 新增 router 時產生「忘記加」的空間。US2／US3 的 admin_stores 與
# admin_menu_items 於此處加入。
v1.include_router(admin_session.router)
v1.include_router(admin_stores.router)
v1.include_router(admin_menu_items.router)

app.include_router(v1)

（stores.router 放在一般使用者端點那一段，admin_* 維持獨立的管理端區塊，兩邊都保留，順序合理）

二、backend/app/core/config.py

同樣兩段都留,直接接在一起:

python
    # --- 推薦餐廳（第二輪）---
    #
    # 兩個值集中於此而非散落在服務層：半徑是暫定值（OQ-7），實地測試後
    # 很可能調整，散落多處會漏改。
    #
    #: 「附近」的距離上限（公里）。超過此距離的店家不出現在距離排序清單中，
    #: 即使範圍內不足 nearby_limit 家也不以範圍外的店家補足（spec FR-020）。
    nearby_radius_km: float = 5.0
    #: 距離排序清單的回傳筆數上限（spec FR-014）。
    nearby_limit: int = 10

    # --- 管理員名單（第三輪，憲章原則 IV）---
    #
    # 管理員身分**只能**由此設定指派，系統中不存在任何可寫入 users.role
    # 的 API。登入時（services/admin_roles.py）以此名單核對並**雙向同步**：
    # 在名單內 → admin，不在名單內 → user。
    #
    # ⚠ 因為是雙向同步，**直接改資料庫授予 admin 無效**（下次登入被覆寫）。
    #    資料庫直改僅能作為緊急撤銷手段，且撤銷後必須同步移出本名單，
    #    否則下次登入即復原。
    #
    # ⚠ 格式為**半形逗號分隔的字串**，不是 JSON 陣列——pydantic-settings
    #    對 list[str] 欄位要求環境變數為 JSON，而引號在 .env、docker-compose
    #    與 Vercel 環境變數面板中都容易被吃掉或轉義錯誤。
    #
    # 留空 = 無人是管理員（後台無人可進入），而非全體開放。
    admin_line_user_ids: str = ""
三、處理完後標記解決
bash
git add backend/app/main.py backend/app/core/config.py
四、還剩三個

麻煩貼出:

bash
git diff frontend/src/lib/api/endpoints.ts
git diff frontend/src/lib/api/types.ts
git diff .specify/feature.json

前兩個我預期也是「兩邊各自新增、都要保留」的模式,跟這次一樣處理;.specify/feature.json 應該是最單純的,貼出來一起確認完就可以 git add . && git commit 收尾了。

PS C:\Users\user\Desktop\dev\speckit-agy\Caluli> git diff frontend/src/lib/api/endpoints.ts diff --cc frontend/src/lib/api/endpoints.ts index 1013d5d,3e913eb..0000000 --- a/frontend/src/lib/api/endpoints.ts +++ b/frontend/src/lib/api/endpoints.ts @@@ -69,27 -72,40 +75,66 @@@ export const foodAp

PASTED

Reconciled type naming conflicts and restructured API schemas
Reconciled type naming conflicts and restructured API schemas

這裡出現一個真正需要你決定的衝突,不能單純兩邊都留——兩輪各自定義了同名但內容不同的 Store 和 MenuItem,如果原封不動兩邊都留,TypeScript 會出現重複宣告的編譯錯誤。分開講。

一、endpoints.ts:安全,兩段直接接起來就好

storeApi(第二輪)跟 adminApi(第三輪)是兩個獨立的物件,沒有互相衝突,直接刪掉衝突標記、兩段都保留即可。等一下 types.ts 改完型別名稱後,這裡也要跟著微調(見下面第三步)。

二、types.ts:真正的衝突,需要重新命名

第二輪定義了給一般使用者查詢用的 Store(含 distance_m)跟 MenuItem(欄位叫 calories_kcal);第三輪定義了給管理員後台用的 Store(含 created_at/updated_at,沒有 distance_m)跟 MenuItem(欄位叫 calories,沒有 _kcal 字尾)。

這其實反映一個合理的事實:這兩組型別對應到後端兩個不同的 API 回應格式(使用者端讀取 API vs 管理員 CRUD API),欄位本來就不必然一樣。但同一支檔案裡不能有兩個同名 interface Store,所以要把第三輪(管理端)的型別加上 Admin 前綴來區分,不是誰對誰錯、不是刪掉一邊。

打開 types.ts,把整段衝突改成:

typescript
// ---------------------------------------------------------------------------
// 推薦餐廳（第二輪，唯讀）
// ---------------------------------------------------------------------------

export interface Store {
  id: string
  /**
   * 店家名稱。**不具唯一性**——連鎖分店同名為正常資料。
   * 不得作為識別鍵、React key 或去重依據，一律使用 `id`（FR-016a）。
   */
  name: string
  /** 分辨同名分店的唯一依據，清單必須顯示（FR-016）。 */
  address: string | null
  latitude: number | null
  longitude: number | null
  /**
   * 與使用者當次座標的直線距離（公尺）。
   * `null` 代表**未計算**（全部模式），不代表距離為 0。
   */
  distance_m: number | null
}

export interface StoreListResponse {
  /** 由是否提供座標決定，非客戶端指定。 */
  mode: 'nearby' | 'all'
  radius_km: number | null
  /**
   * 資料庫中的店家總數，不受半徑、筆數上限或座標有效性影響。
   *
   * 用來區分兩種語意完全不同的空狀態（research.md R-05）：
   *   stores 空 + total > 0  → 「附近查無店家」，提供「改看全部店家」
   *   stores 空 + total == 0 → 「目前尚無店家資料」，不提供改看操作
   */
  total_store_count: number
  stores: Store[]
}

export interface MenuItem {
  id: string
  store_id: string
  name: string
  /**
   * 以下四個欄位的 `null` 與 `0` 是**兩種不同的有效狀態**（FR-025）：
   *   null → 店家未提供 → 顯示「無資料」
   *   0    → 店家登錄為零 → 顯示 0
   *
   * ⚠ 型別**必須**是 `number | null`。寫成 `number` 會讓「無資料」分支
   * 在型別上看起來不可能發生，而它其實是常態。
   */
  calories_kcal: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
}

export interface MenuItemListResponse {
  /** 空陣列代表該店尚未登錄餐點，屬正常結果而非錯誤（FR-024）。 */
  menu_items: MenuItem[]
}

// ─── 管理端（第三輪）────────────────────────────────────────────────
// 對應 specs/003-admin-backoffice/contracts/admin-api.yaml
// ⚠ 這裡的型別統一加上 Admin 前綴，與上方第二輪唯讀查詢用的 Store／MenuItem
// 刻意區分——兩者對應後端不同的 API 回應格式（欄位命名、數值精度皆不同），
// 不是同一份資料的重複定義，不可合併或互相取代。

/** GET /admin/me 的回應。非管理員拿不到 200，故 role 必為 'admin'。 */
export interface AdminSession {
  user_id: string
  display_name: string | null
  role: 'admin'
}

/**
 * 數值欄位為 **number**（2026-08-04 與第二輪定案）。
 *
 * 後端回應 schema 用 `float` 而非 `Decimal`——Decimal 在 pydantic v2 會
 * 序列化成字串，而字串會讓 `value.toFixed(1)` 直接 TypeError（第二輪就是
 * 這樣炸掉整頁的）。後端有 isinstance 斷言擋著這種退化。
 */
export interface AdminStore {
  id: string
  name: string
  address: string
  /** null = 未設定座標，該店家不會出現在使用者端的附近店家推薦中。 */
  latitude: number | null
  longitude: number | null
  created_at: string
  updated_at: string
}

export interface AdminStoreWithCount extends AdminStore {
  /** 刪除確認提示的「將一併刪除 N 道餐點」取自此欄位。 */
  menu_item_count: number
}

/** 送出時可用 number；留空的座標送 null（必須成對）。 */
export interface AdminStoreInput {
  name: string
  address: string
  latitude: number | null
  longitude: number | null
}

/**
 * 店家菜單上的餐點（管理端視角）。
 *
 * ⚠ **null ≠ 0**：null 代表店家未提供，0 代表確實為零。呈現時必須區分，
 * 不得把 null 顯示成 0（FR-033）。不要用 `value || '—'` 這種寫法，
 * 那會把 0 也當成假值。
 *
 * ⚠ 欄位名稱是 `calories`（不是 `calories_kcal`）。這支是管理端直接對應
 * 資料庫欄位的型別；上方第二輪的 `MenuItem.calories_kcal` 是使用者端 API
 * 回應層轉換過的命名，兩者是不同端點的不同回應格式，不需要（也不應該）
 * 統一成同一個名稱。
 */
export interface AdminMenuItem {
  id: string
  store_id: string
  name: string
  calories: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  created_at: string
  updated_at: string
}

/**
 * 送出餐點。四個營養欄位彼此獨立，皆可為 null（＝未提供）。
 * 送 0 與送 null 是不同的意思，表單不得把空欄位轉成 0。
 */
export interface AdminMenuItemInput {
  name: string
  calories: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
}
三、回頭修正 endpoints.ts 裡 adminApi 引用的型別名稱

因為上一步把管理端型別都加了 Admin 前綴,endpoints.ts 裡 adminApi 那段原本寫 StoreInput、Store、StoreWithCount、MenuItem、MenuItemInput 的地方,要跟著改成 AdminStoreInput、AdminStore、AdminStoreWithCount、AdminMenuItem、AdminMenuItemInput:

typescript
export const adminApi = {
  me: () => api.get<AdminSession>('/admin/me'),

  stores: {
    list: () => api.get<{ stores: AdminStoreWithCount[] }>('/admin/stores'),
    create: (input: AdminStoreInput) => api.post<AdminStore>('/admin/stores', input),
    update: (id: string, input: Partial<AdminStoreInput>) =>
      api.patch<AdminStore>(`/admin/stores/${id}`, input),
    remove: (id: string) => api.delete<void>(`/admin/stores/${id}`),
    get: (id: string) => api.get<AdminStore>(`/admin/stores/${id}`),
  },

  menuItems: {
    list: (storeId: string) =>
      api.get<{ menu_items: AdminMenuItem[] }>(`/admin/stores/${storeId}/menu-items`),
    create: (storeId: string, input: AdminMenuItemInput) =>
      api.post<AdminMenuItem>(`/admin/stores/${storeId}/menu-items`, input),
    update: (id: string, input: Partial<AdminMenuItemInput>) =>
      api.patch<AdminMenuItem>(`/admin/menu-items/${id}`, input),
    remove: (id: string) => api.delete<void>(`/admin/menu-items/${id}`),
  },
}

storeApi 那段(第二輪)維持原樣不用改。

四、.specify/feature.json

這個影響很小,只是 spec-kit 記錄「目前作用中的 feature」,不影響程式碼運作。因為你現在正在把 main(含第三輪)合併進第二輪分支,建議先保留第二輪的值,之後合併回 main、要開始下一輪時再手動更新:

bash
git checkout --ours .specify/feature.json
git add .specify/feature.json
五、全部處理完後
bash
git add backend/app/main.py backend/app/core/config.py frontend/src/lib/api/endpoints.ts frontend/src/lib/api/types.ts
git status

確認沒有任何 Unmerged paths 之後:

bash
git commit

commit 完之後,強烈建議做一次 TypeScript 編譯檢查(例如 npm run build 或 tsc --noEmit),確認改完型別名稱後,原本第二輪程式碼裡有沒有其他地方也用到 Store/MenuItem 但實際上該指向 AdminStore/AdminMenuItem 的(如果有,編譯器會直接報錯告訴你哪一行型別對不上),這樣才能保證重新命名沒有遺漏。