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
// 推薦餐廳（第二輪）
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
