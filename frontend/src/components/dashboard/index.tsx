'use client'

/** 儀表板元件群（T092–T096）。 */

import { EmptyState } from '@/components/ui/feedback'
import { useMealPhoto } from '@/hooks/useMealPhoto'
import type { DashboardResponse, MealRecord, Nutrients } from '@/lib/api/types'
import { formatGrams, formatKcal } from '@/lib/nutrition'

export type ViewMode = 'consumed' | 'remaining'

const MEAL_LABELS: Record<string, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
  snack: '點心',
}

/** T092：熱量主卡。超標時明確標示（FR-048）。 */
export function CalorieHeroCard({
  data,
  mode,
}: {
  data: DashboardResponse
  mode: ViewMode
}) {
  const target = data.targets.calories_kcal
  const consumed = data.consumed.calories_kcal
  const percent = target > 0 ? Math.min(100, (consumed / target) * 100) : 0
  const shown = mode === 'consumed' ? consumed : Math.max(0, data.remaining.calories_kcal)

  return (
    <div className="relative overflow-hidden rounded-3xl border border-slate-800/80 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-950 p-5 text-white shadow-xl">
      <div className="mb-4 flex items-center justify-between">
        <span className="rounded-full border border-brand-800/50 bg-brand-950/80 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-brand-400">
          熱量指標
        </span>
        <span className="numeric-stable rounded-full border border-slate-700/80 bg-slate-800/90 px-3 py-1 text-xs font-semibold text-slate-300">
          目標: {formatKcal(target)} kcal
        </span>
      </div>

      <div className="flex items-end justify-between">
        <div>
          <div className="numeric-stable text-4xl font-black tracking-tight">
            {formatKcal(shown)}
            <span className="ml-1 text-sm font-medium text-slate-400">kcal</span>
          </div>
          <div className="mt-1 text-xs font-medium text-slate-400">
            {mode === 'consumed' ? '今日已攝入熱量' : '今日剩餘可用熱量'}
          </div>
        </div>
        <div className="numeric-stable shrink-0 text-right">
          <div className="text-xs text-slate-400">達成率</div>
          <div className="text-lg font-black">{Math.round(percent)}%</div>
        </div>
      </div>

      <div className="mt-4 h-2.5 w-full overflow-hidden rounded-full border border-slate-700/30 bg-slate-800/80">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            data.over_target
              ? 'bg-gradient-to-r from-rose-500 to-orange-400'
              : 'bg-gradient-to-r from-brand-500 via-emerald-400 to-teal-300'
          }`}
          style={{ width: `${percent}%` }}
        />
      </div>

      {data.over_target && (
        <p className="mt-3 rounded-2xl bg-rose-950/60 px-3 py-2 text-[11px] font-bold text-rose-300">
          已超出每日建議熱量 {formatKcal(Math.abs(data.remaining.calories_kcal))} kcal
        </p>
      )}
    </div>
  )
}

/** T093：三大營養素卡片。 */
export function MacroCards({
  consumed,
  targets,
  remaining,
  mode,
}: {
  consumed: Nutrients
  targets: Nutrients
  remaining: Nutrients
  mode: ViewMode
}) {
  const macros = [
    { key: 'protein_g', label: '蛋白質', color: 'bg-indigo-500', text: 'text-indigo-500' },
    { key: 'carbs_g', label: '碳水化合物', color: 'bg-amber-500', text: 'text-amber-500' },
    { key: 'fat_g', label: '脂肪', color: 'bg-rose-500', text: 'text-rose-500' },
  ] as const

  return (
    <div className="grid grid-cols-3 gap-2.5">
      {macros.map((macro) => {
        const done = consumed[macro.key]
        const goal = targets[macro.key]
        const left = Math.max(0, remaining[macro.key])
        const percent = goal > 0 ? Math.min(100, (done / goal) * 100) : 0

        return (
          <div
            key={macro.key}
            className="flex flex-col justify-between rounded-2xl border border-slate-200/70 bg-white p-3.5 shadow-sm dark:border-slate-800/80 dark:bg-slate-900/80"
          >
            <div className="mb-1.5 flex items-center justify-between">
              <span className={`h-2.5 w-2.5 rounded-full ${macro.color}`} />
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                {macro.label}
              </span>
            </div>
            <div className="my-1">
              <div className="numeric-stable text-lg font-black">
                {formatGrams(mode === 'consumed' ? done : left)}g
              </div>
              <div className="numeric-stable text-[10px] font-medium text-slate-400">
                {mode === 'consumed' ? '已攝取' : '尚缺'} / {formatGrams(goal)}g
              </div>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div className={`h-full rounded-full ${macro.color}`} style={{ width: `${percent}%` }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** T094：已攝取／尚缺視角切換（FR-047）。 */
export function ViewModeToggle({
  mode,
  onChange,
}: {
  mode: ViewMode
  onChange: (mode: ViewMode) => void
}) {
  return (
    <div className="flex items-center rounded-2xl border border-slate-300/50 bg-slate-200/70 p-1 shadow-inner dark:border-slate-700/50 dark:bg-slate-800/80">
      {(['consumed', 'remaining'] as const).map((value) => (
        <button
          key={value}
          type="button"
          onClick={() => onChange(value)}
          aria-pressed={mode === value}
          className={`rounded-xl px-3 py-1 text-xs font-bold transition ${
            mode === value
              ? 'bg-white text-slate-800 shadow-sm dark:bg-slate-700 dark:text-white'
              : 'text-slate-500 dark:text-slate-400'
          }`}
        >
          {value === 'consumed' ? '已攝取' : '尚缺'}
        </button>
      ))}
    </div>
  )
}

/** T095：日期切換條（FR-050）。 */
export function DateStrip({
  selected,
  onSelect,
}: {
  selected: string
  onSelect: (date: string) => void
}) {
  const days = Array.from({ length: 7 }, (_, index) => {
    const d = new Date()
    d.setDate(d.getDate() - (6 - index))
    return d
  })
  const iso = (d: Date) => d.toISOString().slice(0, 10)

  return (
    <div className="no-scrollbar flex items-center gap-1.5 overflow-x-auto py-0.5">
      {days.map((day) => {
        const value = iso(day)
        const active = value === selected
        return (
          <button
            key={value}
            type="button"
            onClick={() => onSelect(value)}
            aria-current={active ? 'date' : undefined}
            className={`flex min-w-[44px] flex-1 flex-col items-center rounded-2xl py-2 text-[10px] font-bold transition ${
              active
                ? 'bg-brand-500 text-white shadow-md'
                : 'bg-white text-slate-500 dark:bg-slate-900 dark:text-slate-400'
            }`}
          >
            <span>{['日', '一', '二', '三', '四', '五', '六'][day.getDay()]}</span>
            <span className="numeric-stable mt-0.5 text-sm font-black">{day.getDate()}</span>
          </button>
        )
      })}
    </div>
  )
}

/** T096：當日紀錄清單（FR-049）。 */
export function MealList({
  records,
  onEdit,
  onDelete,
}: {
  records: MealRecord[]
  onEdit: (record: MealRecord) => void
  onDelete: (record: MealRecord) => void
}) {
  if (records.length === 0) {
    return (
      <EmptyState
        icon="🍽️"
        title="這一天還沒有紀錄"
        actionHref="/capture"
        actionLabel="拍照記帳"
      />
    )
  }

  return (
    <ul className="space-y-3">
      {records.map((record) => (
        <MealListItem key={record.id} record={record} onEdit={onEdit} onDelete={onDelete} />
      ))}
    </ul>
  )
}

function MealListItem({
  record,
  onEdit,
  onDelete,
}: {
  record: MealRecord
  onEdit: (record: MealRecord) => void
  onDelete: (record: MealRecord) => void
}) {
  const photoUrl = useMealPhoto(record.id, record.has_photo)

  return (
    <li className="rounded-3xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-3">
        {photoUrl && (
          <img
            src={photoUrl}
            alt=""
            className="h-14 w-14 shrink-0 rounded-2xl object-cover"
          />
        )}
        <div className="min-w-0 flex-1">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500 dark:bg-slate-800">
            {MEAL_LABELS[record.meal_type] ?? record.meal_type}
          </span>
          <p className="mt-1.5 truncate text-sm font-black">
            {record.items.map((item) => item.food_name).join('、') || '（無品項）'}
          </p>
          <p className="numeric-stable mt-1 text-[11px] text-slate-400">
            蛋白質 {formatGrams(record.totals.protein_g)}g ・ 碳水{' '}
            {formatGrams(record.totals.carbs_g)}g ・ 脂肪 {formatGrams(record.totals.fat_g)}g
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="numeric-stable text-base font-black text-brand-600 dark:text-brand-400">
            {formatKcal(record.totals.calories_kcal)}
            <span className="ml-0.5 text-[10px] font-medium text-slate-400">kcal</span>
          </p>
        </div>
      </div>

      <div className="mt-3 flex gap-2 border-t border-slate-100 pt-2.5 dark:border-slate-800">
        <button
          type="button"
          onClick={() => onEdit(record)}
          className="flex-1 rounded-xl py-1.5 text-[11px] font-bold text-slate-500 transition hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          編輯
        </button>
        <button
          type="button"
          onClick={() => onDelete(record)}
          className="flex-1 rounded-xl py-1.5 text-[11px] font-bold text-rose-500 transition hover:bg-rose-50 dark:hover:bg-rose-950/40"
        >
          刪除
        </button>
      </div>
    </li>
  )
}
