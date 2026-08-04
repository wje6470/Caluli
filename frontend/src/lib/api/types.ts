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

// ─── 管理端（第三輪）────────────────────────────────────────────────
// 對應 specs/003-admin-backoffice/contracts/admin-api.yaml
// 店家與餐點的型別於 US2／US3 加入。

/** GET /admin/me 的回應。非管理員拿不到 200，故 role 必為 'admin'。 */
export interface AdminSession {
  user_id: string
  display_name: string | null
  role: 'admin'
}

/**
 * ⚠️ 數值欄位為 **string** 而非 number。
 *
 * 後端 schema 以 Decimal 宣告（避免浮點誤差），pydantic v2 將 Decimal
 * 序列化為字串以保留精度，因此線路上收到的是 "25.039600" 這種字串。
 * 這是全專案既有行為，第一輪的 height_cm 等欄位同樣如此——只是第一輪的
 * 型別宣告寫成 number，與實際不符（既有落差，修正需一併處理第一輪）。
 *
 * 此處如實宣告為 string，需要運算時明確 Number() 轉換，不要假設它是數字。
 */
export interface Store {
  id: string
  name: string
  address: string
  /** null = 未設定座標，該店家不會出現在使用者端的附近店家推薦中。 */
  latitude: string | null
  longitude: string | null
  created_at: string
  updated_at: string
}

export interface StoreWithCount extends Store {
  /** 刪除確認提示的「將一併刪除 N 道餐點」取自此欄位。 */
  menu_item_count: number
}

/** 送出時可用 number；留空的座標送 null（必須成對）。 */
export interface StoreInput {
  name: string
  address: string
  latitude: number | null
  longitude: number | null
}

/**
 * 店家菜單上的餐點。
 *
 * ⚠️ 營養欄位為 `string | null`，兩層意義都要注意：
 *   - string 而非 number：同上，Decimal 序列化為字串
 *   - **null ≠ 0**：null 代表店家未提供，0 代表確實為零。
 *     呈現時必須區分，不得把 null 顯示成 0（FR-033）。
 */
export interface MenuItem {
  id: string
  store_id: string
  name: string
  calories: string | null
  protein_g: string | null
  carbs_g: string | null
  fat_g: string | null
  created_at: string
  updated_at: string
}

/**
 * 送出餐點。四個營養欄位彼此獨立，皆可為 null（＝未提供）。
 * 送 0 與送 null 是不同的意思，表單不得把空欄位轉成 0。
 */
export interface MenuItemInput {
  name: string
  calories: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
}
