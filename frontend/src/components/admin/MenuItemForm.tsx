'use client'

/**
 * 餐點新增／編輯表單。
 *
 * ★ 這個表單唯一容易寫錯的地方：留空 ≠ 0
 * ======================================
 * 空欄位必須送 null，不能送 0。以 0 送出會讓「店家未提供」與「確實為 0」
 * 的區別在寫入當下永久喪失（FR-032）。
 *
 * 因此欄位一律以**字串**保存表單狀態（空字串＝未提供），只在送出時才轉成
 * number 或 null——用 number 型別的 state 會逼你替空值選一個數字，那就錯了。
 */

import { useState } from 'react'

import { Modal } from '@/components/ui/Modal'
import type { MenuItem, MenuItemInput } from '@/lib/api/types'

type Props = {
  item: MenuItem | null
  onSubmit: (input: MenuItemInput) => void
  onCancel: () => void
  pending: boolean
  error: string | null
}

const NUTRITION = [
  { key: 'calories', label: '熱量', unit: '大卡' },
  { key: 'protein_g', label: '蛋白質', unit: '公克' },
  { key: 'carbs_g', label: '碳水化合物', unit: '公克' },
  { key: 'fat_g', label: '脂肪', unit: '公克' },
] as const

type NutritionKey = (typeof NUTRITION)[number]['key']

const label = 'block text-sm font-medium text-slate-700'
const input =
  'mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

export function MenuItemForm({ item, onSubmit, onCancel, pending, error }: Props) {
  const [name, setName] = useState(item?.name ?? '')
  // API 回傳 number | null；表單以字串保存（空字串＝未提供）。
  // ⚠️ 必須用 `?? ''` 而非 `|| ''`——數值 0 是合法且有意義的值，
  //    用 || 會把「確實為 0」的餐點誤顯示成空欄位，儲存後就變成「未提供」。
  const toField = (value: number | null | undefined): string =>
    value === null || value === undefined ? '' : value.toString()

  const [values, setValues] = useState<Record<NutritionKey, string>>({
    calories: toField(item?.calories),
    protein_g: toField(item?.protein_g),
    carbs_g: toField(item?.carbs_g),
    fat_g: toField(item?.fat_g),
  })
  const [localError, setLocalError] = useState<string | null>(null)

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setLocalError(null)

    for (const { key, label: fieldLabel } of NUTRITION) {
      const raw = values[key].trim()
      if (raw === '') continue
      const parsed = Number(raw)
      if (Number.isNaN(parsed)) {
        setLocalError(`${fieldLabel}必須是數字。`)
        return
      }
      if (parsed < 0) {
        setLocalError(`${fieldLabel}不得為負數。`)
        return
      }
    }

    // ★ 空字串 → null（未提供），不是 0。
    const toValue = (raw: string): number | null => (raw.trim() === '' ? null : Number(raw))

    onSubmit({
      name: name.trim(),
      calories: toValue(values.calories),
      protein_g: toValue(values.protein_g),
      carbs_g: toValue(values.carbs_g),
      fat_g: toValue(values.fat_g),
    })
  }

  const message = localError ?? error

  return (
    <Modal onClose={onCancel} title={item ? '編輯餐點' : '新增餐點'} variant="center">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={label} htmlFor="item-name">
            餐點名稱
          </label>
          <input
            id="item-name"
            className={input}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          {NUTRITION.map(({ key, label: fieldLabel, unit }) => (
            <div key={key}>
              <label className={label} htmlFor={`item-${key}`}>
                {fieldLabel}（{unit}）
              </label>
              <input
                id={`item-${key}`}
                className={input}
                value={values[key]}
                onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder="未提供"
                inputMode="decimal"
              />
            </div>
          ))}
        </div>

        {/* FR-032：留空與填 0 的語意不同，必須明確告知管理員。 */}
        <div className="rounded border border-sky-200 bg-sky-50 p-3 text-xs text-sky-900">
          <p className="font-medium">關於營養數值</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            <li>
              <strong>留空</strong>＝店家未提供此項數值，使用者端會顯示「無資料」。
            </li>
            <li>
              <strong>填 0</strong>＝該項確實為零（例如零卡飲料的熱量），使用者端會顯示 0。
            </li>
            <li>兩者意思不同，請勿用 0 代替「不知道」——之後無法分辨。</li>
            <li>四個欄位彼此獨立，可以只填其中幾項。</li>
          </ul>
        </div>

        {message && (
          <p
            role="alert"
            className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700"
          >
            {message}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-300 px-4 py-2 text-sm"
          >
            取消
          </button>
          <button
            type="submit"
            disabled={pending}
            className="rounded bg-slate-800 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {pending ? '儲存中…' : '儲存'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
