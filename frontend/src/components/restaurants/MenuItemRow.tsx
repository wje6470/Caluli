'use client'

/**
 * 單一餐點的營養呈現。
 *
 * ★ 本輪最容易寫錯的一行程式就在這裡（FR-025）
 * ==============================================
 * `null` 與 `0` 是兩種不同的有效狀態，必須雙向區分：
 *
 *   null → 店家未提供 → 顯示「無資料」
 *   0    → 店家登錄該營養素為零 → 顯示 0
 *
 * ⚠️ `0` 是 falsy。以下寫法**全都是錯的**，且不會拋任何錯誤：
 *
 *     value or '無資料'
 *     value ? fmt(value) : '無資料'
 *     {value && <span>{value}</span>}
 *     value ?? '無資料'   ← 這個對 null 正確，但對 undefined 也會觸發
 *
 * 必須以 `=== null` 明確判斷。tests/unit/menu-item.test.tsx 存在的唯一理由
 * 就是抓這個誤判；seed 資料中那筆「無糖清茶」（四欄皆為 0）也是為此而放。
 */

import type { MenuItem } from '@/lib/api/types'

const NO_DATA = '無資料'

/** null → 「無資料」；0 → 「0」。刻意不使用 || 或 ?? 以外的簡寫。 */
function formatNutrient(value: number | null, unit: string): string {
  if (value === null) return NO_DATA
  // 去掉無意義的小數（30.00 → 30，30.20 → 30.2）。
  const text = Number.isInteger(value) ? String(value) : String(Number(value.toFixed(1)))
  return `${text}${unit}`
}

export function MenuItemRow({ item }: { item: MenuItem }) {
  const calories = formatNutrient(item.calories_kcal, ' kcal')

  return (
    <article className="rounded-2xl border border-slate-200/80 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-bold">{item.name}</h3>
        <p
          className={`numeric-stable shrink-0 text-sm font-black ${
            item.calories_kcal === null ? 'text-slate-400' : 'text-brand-600 dark:text-brand-400'
          }`}
        >
          {calories}
        </p>
      </div>

      <dl className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
        <Nutrient label="蛋白質" value={item.protein_g} />
        <Nutrient label="碳水" value={item.carbs_g} />
        <Nutrient label="脂肪" value={item.fat_g} />
      </dl>
    </article>
  )
}

function Nutrient({ label, value }: { label: string; value: number | null }) {
  const missing = value === null

  return (
    <div className="rounded-xl bg-slate-50 px-2 py-1.5 dark:bg-slate-800/60">
      <dt className="font-bold text-slate-400">{label}</dt>
      <dd
        className={`numeric-stable font-black ${
          missing ? 'text-slate-400' : 'text-slate-700 dark:text-slate-200'
        }`}
      >
        {formatNutrient(value, ' g')}
      </dd>
    </div>
  )
}
