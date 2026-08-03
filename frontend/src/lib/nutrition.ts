/**
 * 份量換算（前端即時計算）。
 *
 * ★ FR-032 / SC-003：使用者調整份量時，畫面必須**立即**更新，
 *   且**不得**發出任何 API 請求。任何網路往返都無法穩定達成 0.3 秒。
 *
 * 公式與後端 services/nutrition.py 相同。後端在儲存時會以同一公式重新
 * 驗算，客戶端數值不被採信——這裡算出來的只用於畫面回饋。
 */

import type { Nutrients, Per100g } from '@/lib/api/types'

export const MIN_PORTION_GRAMS = 1
export const MAX_PORTION_GRAMS = 5000

/** 依份量換算單一品項的營養值。 */
export function scaleNutrients(per100g: Per100g, grams: number): Nutrients {
  const factor = grams / 100
  return {
    calories_kcal: per100g.calories_kcal * factor,
    protein_g: per100g.protein_g * factor,
    carbs_g: per100g.carbs_g * factor,
    fat_g: per100g.fat_g * factor,
  }
}

export const ZERO_NUTRIENTS: Nutrients = {
  calories_kcal: 0,
  protein_g: 0,
  carbs_g: 0,
  fat_g: 0,
}

/** 加總多個品項（FR-033：任一品項變動時合計同步更新）。 */
export function sumNutrients(items: Nutrients[]): Nutrients {
  return items.reduce(
    (total, item) => ({
      calories_kcal: total.calories_kcal + item.calories_kcal,
      protein_g: total.protein_g + item.protein_g,
      carbs_g: total.carbs_g + item.carbs_g,
      fat_g: total.fat_g + item.fat_g,
    }),
    ZERO_NUTRIENTS
  )
}

/** 份量上下限約束（FR-034）。非數字或超出範圍時夾回合法值。 */
export function clampPortion(grams: number): number {
  if (!Number.isFinite(grams)) return MIN_PORTION_GRAMS
  return Math.min(MAX_PORTION_GRAMS, Math.max(MIN_PORTION_GRAMS, grams))
}

/** 熱量顯示取整；營養素取一位小數。 */
export const formatKcal = (value: number): string => Math.round(value).toLocaleString()
export const formatGrams = (value: number): string => (Math.round(value * 10) / 10).toFixed(1)
