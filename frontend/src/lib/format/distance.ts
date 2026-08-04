/**
 * 距離呈現格式（推薦餐廳模組，第二輪）。
 *
 * 後端回傳的是公尺整數；此處只負責呈現，不做任何計算。
 *
 * 註：距離為**直線距離**（大圓距離），非道路或步行距離——都會區的實際
 * 步行距離約為此值的 1.3〜1.5 倍。spec 的 5 公里上限亦以直線距離認定。
 */

/**
 * 公尺 → 可讀字串。
 *
 * 1 公里以下顯示公尺（取整至十位，避免呈現不存在的精度）；
 * 1 公里以上顯示公里至小數一位。
 */
export function formatDistance(metres: number): string {
  if (!Number.isFinite(metres) || metres < 0) return ''

  if (metres < 1000) {
    const rounded = Math.round(metres / 10) * 10
    return `${rounded} 公尺`
  }

  return `${(metres / 1000).toFixed(1)} 公里`
}
