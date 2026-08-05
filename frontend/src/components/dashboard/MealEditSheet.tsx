'use client'

/** T107：編輯既有紀錄（FR-042）。份量調整同樣是前端即時重算。 */

import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { PortionSlider } from '@/components/capture/PortionSlider'
import { Modal } from '@/components/ui/Modal'
import { useMealPhoto } from '@/hooks/useMealPhoto'
import { mealRecordApi } from '@/lib/api/endpoints'
import type { MealRecord, MealType } from '@/lib/api/types'
import { formatGrams, formatKcal, scaleNutrients, sumNutrients } from '@/lib/nutrition'

const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: 'breakfast', label: '早餐' },
  { value: 'lunch', label: '午餐' },
  { value: 'dinner', label: '晚餐' },
  { value: 'snack', label: '點心' },
]

type EditItem = {
  id: string
  name: string
  grams: number
  defaultGrams: number | null
  per100g: MealRecord['items'][number]['per_100g']
  foodReferenceId: string | null
}

export function MealEditSheet({
  record,
  onClose,
  onSaved,
}: {
  record: MealRecord
  onClose: () => void
  onSaved: () => void
}) {
  const [mealType, setMealType] = useState<MealType>(record.meal_type)
  const [items, setItems] = useState<EditItem[]>(
    record.items.map((item) => ({
      id: item.id,
      name: item.food_name,
      grams: item.portion_grams,
      defaultGrams: item.default_portion_grams,
      per100g: item.per_100g,
      foodReferenceId: item.food_reference_id,
    }))
  )

  const totals = sumNutrients(items.map((item) => scaleNutrients(item.per100g, item.grams)))
  const photoUrl = useMealPhoto(record.id, record.has_photo)

  const save = useMutation({
    mutationFn: () =>
      mealRecordApi.update(record.id, {
        recognition_id: null,
        meal_type: mealType,
        items: items.map((item) => ({
          food_reference_id: item.foodReferenceId,
          food_name: item.name,
          portion_grams: item.grams,
          default_portion_grams: item.defaultGrams,
          per_100g: item.per100g,
          recognition_confidence: null,
          is_user_modified: true,
        })),
      }),
    onSuccess: onSaved,
  })

  return (
    <Modal title="編輯紀錄" onClose={onClose}>
      <>
        {photoUrl && (
          <img
            src={photoUrl}
            alt="餐點照片"
            className="mb-4 h-40 w-full rounded-3xl object-cover shadow-sm"
          />
        )}

        <div className="mb-4 grid grid-cols-4 gap-2">
          {MEAL_TYPES.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setMealType(option.value)}
              className={`rounded-xl py-2 text-xs font-bold transition ${
                mealType === option.value
                  ? 'bg-brand-500 text-white'
                  : 'bg-slate-100 text-slate-500 dark:bg-slate-800'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <ul className="space-y-3">
          {items.map((item, index) => {
            const nutrients = scaleNutrients(item.per100g, item.grams)
            return (
              <li
                key={item.id}
                className="space-y-3 rounded-3xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="flex items-center justify-between gap-2">
                  <input
                    type="text"
                    value={item.name}
                    aria-label="食物名稱"
                    onChange={(e) =>
                      setItems((prev) =>
                        prev.map((it, i) => (i === index ? { ...it, name: e.target.value } : it))
                      )
                    }
                    className="min-w-0 flex-1 bg-transparent text-sm font-black outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setItems((prev) => prev.filter((_, i) => i !== index))}
                    className="shrink-0 text-[11px] font-bold text-slate-400 hover:text-rose-600"
                  >
                    移除
                  </button>
                </div>

                <PortionSlider
                  grams={item.grams}
                  defaultGrams={item.defaultGrams}
                  label={item.name}
                  onChange={(grams) =>
                    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, grams } : it)))
                  }
                />

                <p className="numeric-stable text-right text-sm font-black text-brand-600 dark:text-brand-400">
                  {formatKcal(nutrients.calories_kcal)} kcal
                </p>
              </li>
            )
          })}
        </ul>

        <div className="mt-4 rounded-2xl bg-slate-100 p-3 text-center dark:bg-slate-900">
          <p className="numeric-stable text-lg font-black">
            合計 {formatKcal(totals.calories_kcal)} kcal
          </p>
          <p className="numeric-stable mt-0.5 text-[11px] text-slate-400">
            蛋白質 {formatGrams(totals.protein_g)}g ・ 碳水 {formatGrams(totals.carbs_g)}g ・ 脂肪{' '}
            {formatGrams(totals.fat_g)}g
          </p>
        </div>

        {save.isError && (
          <p role="alert" className="mt-2 text-center text-xs font-semibold text-rose-600">
            儲存失敗，請再試一次。
          </p>
        )}

        <button
          type="button"
          disabled={items.length === 0 || save.isPending}
          onClick={() => save.mutate()}
          className="mt-4 w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-4 text-sm font-black text-white shadow-brand-glow transition active:scale-95 disabled:opacity-50"
        >
          {save.isPending ? '儲存中…' : '儲存修改'}
        </button>
      </>
    </Modal>
  )
}
