/** 辨識結果確認畫面的草稿模型（尚未儲存）。 */

import type {
  FoodCandidate,
  MealItemInput,
  Nutrients,
  Per100g,
  RecognitionItem,
} from '@/lib/api/types'
import { scaleNutrients, ZERO_NUTRIENTS } from '@/lib/nutrition'

export type DraftItem = {
  key: string
  foodReferenceId: string | null
  name: string
  confidence: number | null
  /** null = 對照表查無資料，改由 manualNutrients 提供數值（FR-037）。 */
  per100g: Per100g | null
  defaultGrams: number | null
  grams: number
  /** 僅在 per100g 為 null 時使用。 */
  manualNutrients: Nutrients
  candidates: FoodCandidate[]
  userModified: boolean
}

const FALLBACK_GRAMS = 100

export function toDraftItems(items: RecognitionItem[]): DraftItem[] {
  return items.map((item, index) => ({
    key: `${index}-${item.name}`,
    foodReferenceId: item.food_reference_id,
    name: item.name,
    confidence: item.confidence,
    per100g: item.nutrition_available ? item.per_100g : null,
    defaultGrams: item.default_portion_grams,
    // 系統設定的預設份量（FR-022），不是模型量測結果。
    grams: item.default_portion_grams ?? FALLBACK_GRAMS,
    manualNutrients: ZERO_NUTRIENTS,
    candidates: item.candidates,
    userModified: false,
  }))
}

export function nutrientsOf(item: DraftItem): Nutrients {
  return item.per100g ? scaleNutrients(item.per100g, item.grams) : item.manualNutrients
}

/**
 * 轉為送出格式。
 *
 * per_100g 一律要送——後端據此重新驗算（客戶端算出的數值不被採信）。
 * 手動輸入的品項把使用者填的絕對值反推為每 100g 基準，讓後端能以
 * 同一公式驗算，資料模型也維持一致。
 */
export function toMealItemInput(item: DraftItem): MealItemInput {
  const grams = item.grams
  const per100g: Per100g = item.per100g ?? {
    calories_kcal: (item.manualNutrients.calories_kcal * 100) / grams,
    protein_g: (item.manualNutrients.protein_g * 100) / grams,
    carbs_g: (item.manualNutrients.carbs_g * 100) / grams,
    fat_g: (item.manualNutrients.fat_g * 100) / grams,
  }

  return {
    food_reference_id: item.foodReferenceId,
    food_name: item.name,
    portion_grams: grams,
    default_portion_grams: item.defaultGrams,
    per_100g: per100g,
    recognition_confidence: item.confidence,
    is_user_modified: item.userModified,
  }
}
