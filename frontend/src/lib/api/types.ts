/**
 * API 型別。對應 specs/001-diet-log-mvp/contracts/openapi.yaml。
 *
 * 契約若異動，此檔須同步更新（可由 openapi.yaml 產生）。
 */

export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'
export type Gender = 'male' | 'female'
export type ActivityLevel = 'low' | 'moderate' | 'high'
export type MetricKey = 'calories' | 'protein' | 'carbs' | 'fat'

/** 辨識資源的狀態。processing 為非同步遷移預留（research.md R-07）。 */
export type RecognitionStatus = 'processing' | 'completed' | 'failed'

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    /** 前端據此決定是否顯示「重試」，不必自行維護 code 對照表。 */
    retryable: boolean
  }
}

export interface User {
  id: string
  display_name: string
  picture_url: string | null
}

export interface SessionResponse {
  access_token: string
  token_type: 'Bearer'
  expires_in: number
  user: User
  profile_completed: boolean
}

export interface HealthProfileInput {
  gender: Gender
  age_years: number
  height_cm: number
  weight_kg: number
  activity_level: ActivityLevel
}

export interface HealthProfile extends HealthProfileInput {
  bmr_kcal: number
  tdee_kcal: number
  target_protein_g: number
  target_carbs_g: number
  target_fat_g: number
  computed_at: string
}

export interface MeResponse {
  user: User
  profile_completed: boolean
  profile: HealthProfile | null
}

export interface Nutrients {
  calories_kcal: number
  protein_g: number
  carbs_g: number
  fat_g: number
}

/**
 * 每 100 公克的原始營養值。
 *
 * ⚠️ 前端的份量即時換算完全依賴此欄位（research.md R-09）。
 * 若後端不回傳，份量調整功能無法運作。
 */
export type Per100g = Nutrients

export interface FoodCandidate {
  food_reference_id: string | null
  name: string
  confidence: number
  default_portion_grams: number | null
  per_100g: Per100g | null
}

export interface FoodReference {
  id: string
  name: string
  default_portion_grams: number
  per_100g: Per100g
}

export interface RecognitionItem {
  food_reference_id: string | null
  name: string
  confidence: number | null
  default_portion_grams: number | null
  per_100g: Per100g | null
  /** false = 對照表查無資料，須標示無法自動換算（FR-037）。 */
  nutrition_available: boolean
  candidates: FoodCandidate[]
  bounding_box: { x: number; y: number; width: number; height: number } | null
}

export interface Recognition {
  id: string
  status: RecognitionStatus
  /** 空陣列 = 未偵測到食物，**仍為 completed**，不是錯誤（FR-027）。 */
  items: RecognitionItem[]
  message: string | null
  retry_count: number
  requested_at: string
  completed_at: string | null
}

export interface MealItemInput {
  food_reference_id: string | null
  food_name: string
  portion_grams: number
  default_portion_grams: number | null
  per_100g: Per100g
  recognition_confidence: number | null
  is_user_modified: boolean
}

export interface MealItem extends MealItemInput {
  id: string
  /** 後端驗算後的權威數值。 */
  nutrients: Nutrients
}

export interface MealRecordInput {
  recognition_id: string | null
  meal_type: MealType
  captured_at?: string
  items: MealItemInput[]
}

export interface MealRecord {
  id: string
  record_date: string
  meal_type: MealType
  captured_at: string
  has_photo: boolean
  items: MealItem[]
  totals: Nutrients
}

export interface DashboardResponse {
  date: string
  targets: Nutrients
  consumed: Nutrients
  /** targets − consumed；超標時為負值，須明確標示（FR-048）。 */
  remaining: Nutrients
  over_target: boolean
  records: MealRecord[]
}

export interface TrendPoint {
  date: string
  value: number
}

export interface TrendResponse {
  range_days: number
  metric: MetricKey
  /** 完整日期序列，無紀錄的日期 value 為 0（FR-054）。 */
  points: TrendPoint[]
  target: number | null
  average: number
  target_achievement_rate: number
}


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
   * ⚠️ 型別**必須**是 `number | null`。寫成 `number` 會讓「無資料」分支
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
// ⚠️ 這裡的型別統一加上 Admin 前綴，與上方第二輪唯讀查詢用的 Store／MenuItem
// 刻意區分——兩者對應後端不同的 API 回應格式（欄位命名、是否含時間戳與
// distance_m 皆不同），不是同一份資料的重複定義，不可合併或互相取代。

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
 *
 * ⚠️ 第一輪的欄位（height_cm 等）目前仍回字串，但型別宣告是 number——
 * 那是既有落差，不在本輪範圍。碰到第一輪的數值時仍要小心。
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
 * ⚠️ **null ≠ 0**：null 代表店家未提供，0 代表確實為零。呈現時必須區分，
 * 不得把 null 顯示成 0（FR-033）。特別注意不要用 `value || '—'` 這種寫法，
 * 那會把 0 也當成假值。
 *
 * ⚠️ 欄位名稱是 `calories`（不是 `calories_kcal`）。這支是管理端直接對應
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
