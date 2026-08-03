'use client'

/**
 * 份量調整元件。★ FR-031 / FR-034
 *
 * 「份量」欄位必須是**預設值 + 可即時互動調整**的元件，而非唯讀顯示。
 * 滑桿與數值輸入框並存：滑桿適合粗調，輸入框適合精確值。
 *
 * onChange 是同步呼叫——不 debounce、不非同步。任何延遲都會讓
 * SC-003（0.3 秒內更新）失效。
 */

import { useEffect, useState } from 'react'

import { clampPortion, MAX_PORTION_GRAMS, MIN_PORTION_GRAMS } from '@/lib/nutrition'

const SLIDER_MAX = 1000

type Props = {
  grams: number
  defaultGrams: number | null
  onChange: (grams: number) => void
  disabled?: boolean
  label?: string
}

export function PortionSlider({ grams, defaultGrams, onChange, disabled, label }: Props) {
  const adjusted = defaultGrams !== null && Math.abs(grams - defaultGrams) > 0.5

  // 輸入框保留使用者正在輸入的原始字串。若直接把空字串夾成最小值，
  // 使用者清空欄位想重打時會立刻跳成 1，根本打不了字。
  const [draft, setDraft] = useState(String(grams))
  useEffect(() => {
    setDraft(String(grams))
  }, [grams])

  const commit = (raw: string) => {
    setDraft(raw)
    // 空字串或不完整輸入（如 "."）暫不送出，等使用者打完。
    if (raw.trim() === '') return
    const parsed = Number(raw)
    if (!Number.isFinite(parsed)) return
    onChange(clampPortion(parsed))
  }

  return (
    <div className="space-y-2">
      <div className="flex items-end justify-between">
        <label
          htmlFor={`portion-${label}`}
          className="text-[11px] font-bold uppercase tracking-wider text-slate-400"
        >
          份量
        </label>
        <div className="flex items-center gap-1.5">
          <input
            id={`portion-${label}`}
            type="number"
            inputMode="decimal"
            min={MIN_PORTION_GRAMS}
            max={MAX_PORTION_GRAMS}
            step={5}
            value={draft}
            disabled={disabled}
            aria-label={`${label ?? '品項'}份量（公克）`}
            onChange={(e) => commit(e.target.value)}
            onBlur={() => setDraft(String(grams))}
            className="numeric-stable w-20 rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5 text-right text-sm font-black text-brand-600 outline-none focus:ring-2 focus:ring-brand-500 dark:border-slate-700 dark:bg-slate-800 dark:text-brand-400"
          />
          <span className="text-xs font-bold text-slate-400">g</span>
        </div>
      </div>

      <input
        type="range"
        min={MIN_PORTION_GRAMS}
        max={SLIDER_MAX}
        step={5}
        value={Math.min(grams, SLIDER_MAX)}
        disabled={disabled}
        aria-label={`${label ?? '品項'}份量滑桿`}
        aria-valuetext={`${grams} 公克`}
        onChange={(e) => onChange(clampPortion(Number(e.target.value)))}
        className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-brand-500 disabled:opacity-50 dark:bg-slate-800"
      />

      {defaultGrams !== null && (
        <p className="flex items-center justify-between text-[10px] text-slate-400">
          <span>系統預設 {defaultGrams}g（估計值，非拍照量測）</span>
          {adjusted && (
            <button
              type="button"
              onClick={() => onChange(defaultGrams)}
              className="font-bold text-brand-600 hover:underline dark:text-brand-400"
            >
              回到預設
            </button>
          )}
        </p>
      )}
    </div>
  )
}
