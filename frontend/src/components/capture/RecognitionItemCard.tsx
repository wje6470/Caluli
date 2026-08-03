'use client'

/**
 * 單一辨識品項卡。★ 承載 FR-032、FR-035、FR-036、FR-037
 *
 * 份量變動 → 立即以 scaleNutrients() 重算並重繪。**整個過程沒有任何
 * API 呼叫**——這是 SC-003 的驗收條件（開 Network 分頁應完全靜默）。
 */

import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { foodApi } from '@/lib/api/endpoints'
import type { DraftItem } from '@/lib/capture/draft'
import { formatGrams, formatKcal, scaleNutrients } from '@/lib/nutrition'
import { PortionSlider } from './PortionSlider'

type Props = {
  item: DraftItem
  onChange: (next: DraftItem) => void
  onRemove: () => void
}

export function RecognitionItemCard({ item, onChange, onRemove }: Props) {
  const [expanded, setExpanded] = useState(false)

  // 同步計算——份量一變就是新值，不經 effect、不經網路。
  const nutrients = useMemo(
    () => (item.per100g ? scaleNutrients(item.per100g, item.grams) : item.manualNutrients),
    [item.per100g, item.grams, item.manualNutrients]
  )

  const hasCandidates = item.candidates.length > 1

  return (
    <article className="space-y-3 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <input
            type="text"
            value={item.name}
            aria-label="食物名稱"
            onChange={(e) => onChange({ ...item, name: e.target.value, userModified: true })}
            className="w-full truncate bg-transparent text-sm font-black outline-none"
          />
          {item.confidence !== null && (
            <p className="mt-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
              辨識信心度 {Math.round(item.confidence * 100)}%
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onRemove}
          aria-label={`移除 ${item.name}`}
          className="shrink-0 rounded-xl px-2 py-1 text-[11px] font-bold text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40"
        >
          移除
        </button>
      </header>

      {/* FR-037：查表失敗時明確標示，並允許自行填入 */}
      {!item.per100g && (
        <p className="rounded-2xl bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
          這項食物不在營養資料庫中，無法自動換算。請自行填入熱量與營養素，或移除此項。
        </p>
      )}

      {item.per100g ? (
        <PortionSlider
          grams={item.grams}
          defaultGrams={item.defaultGrams}
          label={item.name}
          onChange={(grams) => onChange({ ...item, grams, userModified: true })}
        />
      ) : (
        <ManualNutrientInputs item={item} onChange={onChange} />
      )}

      <dl className="grid grid-cols-4 gap-2 border-t border-slate-100 pt-3 text-center dark:border-slate-800">
        <Metric label="熱量" value={`${formatKcal(nutrients.calories_kcal)}`} unit="kcal" accent="text-brand-600 dark:text-brand-400" />
        <Metric label="蛋白質" value={formatGrams(nutrients.protein_g)} unit="g" accent="text-indigo-500" />
        <Metric label="碳水" value={formatGrams(nutrients.carbs_g)} unit="g" accent="text-amber-500" />
        <Metric label="脂肪" value={formatGrams(nutrients.fat_g)} unit="g" accent="text-rose-500" />
      </dl>

      {/* FR-035：Top-K 候選改選；FR-037：從營養資料庫搜尋替換 */}
      <div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-[11px] font-bold text-brand-600 hover:underline dark:text-brand-400"
        >
          {expanded ? '收合' : '辨識錯了？換一個'}
        </button>

        {expanded && (
          <>
            <FoodSearchPicker
              onPick={(food) => {
                onChange({
                  ...item,
                  name: food.name,
                  per100g: food.per_100g,
                  defaultGrams: food.default_portion_grams,
                  grams: food.default_portion_grams,
                  foodReferenceId: food.id,
                  confidence: null,
                  userModified: true,
                })
                setExpanded(false)
              }}
            />

            {hasCandidates && (
              <ul className="mt-2 space-y-1.5">
                {item.candidates.map((candidate) => (
                <li key={`${candidate.name}-${candidate.confidence}`}>
                  <button
                    type="button"
                    onClick={() => {
                      // 改選後以新食物的 per_100g 與預設份量重新換算。
                      onChange({
                        ...item,
                        name: candidate.name,
                        per100g: candidate.per_100g,
                        defaultGrams: candidate.default_portion_grams,
                        grams: candidate.default_portion_grams ?? item.grams,
                        foodReferenceId: candidate.food_reference_id,
                        confidence: candidate.confidence,
                        userModified: true,
                      })
                      setExpanded(false)
                    }}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-xs transition ${
                      candidate.name === item.name
                        ? 'bg-brand-50 font-bold text-brand-700 dark:bg-brand-950/50 dark:text-brand-300'
                        : 'bg-slate-50 hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700'
                    }`}
                  >
                    <span>{candidate.name}</span>
                    <span className="numeric-stable text-[10px] text-slate-400">
                      {Math.round(candidate.confidence * 100)}%
                    </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </article>
  )
}

/** T082 / FR-037：從通用食物營養對照表搜尋替換品項。 */
function FoodSearchPicker({
  onPick,
}: {
  onPick: (food: { id: string; name: string; default_portion_grams: number; per_100g: NonNullable<DraftItem['per100g']> }) => void
}) {
  const [term, setTerm] = useState('')
  const query = term.trim()

  const { data, isFetching } = useQuery({
    queryKey: ['foods', query],
    queryFn: () => foodApi.search(query),
    enabled: query.length > 0,
  })

  return (
    <div className="mt-2 space-y-1.5">
      <input
        type="search"
        value={term}
        placeholder="搜尋食物名稱…"
        aria-label="搜尋食物"
        onChange={(e) => setTerm(e.target.value)}
        className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-800"
      />

      {query.length > 0 && (
        <ul className="max-h-40 space-y-1 overflow-y-auto">
          {isFetching && <li className="px-3 py-2 text-[11px] text-slate-400">搜尋中…</li>}
          {!isFetching && data?.foods.length === 0 && (
            <li className="px-3 py-2 text-[11px] text-slate-400">
              找不到符合的食物。您可以直接修改名稱並自行填入營養數值。
            </li>
          )}
          {data?.foods.map((food) => (
            <li key={food.id}>
              <button
                type="button"
                onClick={() => onPick(food)}
                className="flex w-full items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-xs transition hover:bg-slate-100 dark:bg-slate-800 dark:hover:bg-slate-700"
              >
                <span>{food.name}</span>
                <span className="numeric-stable text-[10px] text-slate-400">
                  {Math.round(food.per_100g.calories_kcal)} kcal/100g
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Metric({
  label,
  value,
  unit,
  accent,
}: {
  label: string
  value: string
  unit: string
  accent: string
}) {
  return (
    <div>
      <dt className="text-[10px] font-bold text-slate-400">{label}</dt>
      <dd className={`numeric-stable mt-0.5 text-sm font-black ${accent}`}>
        {value}
        <span className="ml-0.5 text-[10px] font-medium text-slate-400">{unit}</span>
      </dd>
    </div>
  )
}

/** 查無營養資料時的手動輸入（FR-037）。 */
function ManualNutrientInputs({
  item,
  onChange,
}: {
  item: DraftItem
  onChange: (next: DraftItem) => void
}) {
  const fields = [
    { key: 'calories_kcal', label: '熱量 (kcal)' },
    { key: 'protein_g', label: '蛋白質 (g)' },
    { key: 'carbs_g', label: '碳水 (g)' },
    { key: 'fat_g', label: '脂肪 (g)' },
  ] as const

  return (
    <div className="grid grid-cols-2 gap-2">
      {fields.map((field) => (
        <label key={field.key} className="block">
          <span className="mb-1 block text-[10px] font-bold text-slate-400">{field.label}</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={item.manualNutrients[field.key]}
            onChange={(e) =>
              onChange({
                ...item,
                manualNutrients: {
                  ...item.manualNutrients,
                  [field.key]: Math.max(0, Number(e.target.value) || 0),
                },
                userModified: true,
              })
            }
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm font-bold outline-none focus:ring-2 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-800"
          />
        </label>
      ))}
    </div>
  )
}
