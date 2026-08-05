'use client'

/**
 * 首次建檔流程（T063）與 TDEE 結果頁（T064）。
 *
 * 六個步驟：性別 → 年齡 → 身高 → 體重 → 活動量 → 結果。
 * 目標值一律由後端計算後回傳，前端只負責顯示——前後端各算一次會因
 * 四捨五入差異造成畫面與資料庫不一致（research.md R-13）。
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { profileApi } from '@/lib/api/endpoints'
import type { ActivityLevel, Gender, HealthProfile } from '@/lib/api/types'

const ACTIVITY_OPTIONS: { value: ActivityLevel; icon: string; label: string; freq: string; detail: string }[] = [
  { value: 'low', icon: '🛋️', label: '低活動量', freq: '一週 0-1 次', detail: '辦公室久坐內勤' },
  { value: 'moderate', icon: '🚶', label: '中活動量', freq: '一週 2-4 次', detail: '日常有些許規律運動習慣' },
  { value: 'high', icon: '🏃', label: '高活動量', freq: '一週 5-7 次', detail: '高強度訓練或長時站立走動工作' },
]

const TOTAL_STEPS = 6

type Draft = {
  gender: Gender
  age_years: number
  height_cm: number
  weight_kg: number
  activity_level: ActivityLevel
}

const INITIAL: Draft = {
  gender: 'male',
  age_years: 28,
  height_cm: 170,
  weight_kg: 65,
  activity_level: 'moderate',
}

export default function OnboardingPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<Draft>(INITIAL)
  const [result, setResult] = useState<HealthProfile | null>(null)

  const mutation = useMutation({
    mutationFn: () => profileApi.upsert(draft),
    onSuccess: (profile) => {
      setResult(profile)
      queryClient.invalidateQueries({ queryKey: ['me'] })
      setStep(5)
    },
  })

  const patch = (values: Partial<Draft>) => setDraft((prev) => ({ ...prev, ...values }))
  const next = () => (step === 4 ? mutation.mutate() : setStep((s) => s + 1))

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-6 py-6">
      <header className="space-y-3">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0 || step === 5}
            className="text-xs font-bold text-slate-400 disabled:invisible"
          >
            ← 上一步
          </button>
          <span className="numeric-stable rounded-full bg-brand-50 px-3 py-1 text-[11px] font-black text-brand-600 dark:bg-brand-950/80 dark:text-brand-400">
            步驟 {step + 1} / {TOTAL_STEPS}
          </span>
          <span className="w-12" />
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
          <div
            className="h-full bg-gradient-to-r from-brand-600 to-emerald-400 transition-all duration-300"
            style={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%` }}
          />
        </div>
      </header>

      <div className="my-auto py-6">
        {step === 0 && (
          <StepShell icon="🧍" title="生理基本資訊" hint="用於計算基礎代謝率（BMR）">
            <div className="grid grid-cols-2 gap-3">
              {(['male', 'female'] as const).map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => patch({ gender: g })}
                  className={`rounded-3xl border-2 py-6 text-sm font-bold transition ${
                    draft.gender === g
                      ? 'border-brand-500 bg-brand-50/60 dark:bg-brand-950/40'
                      : 'border-slate-200 dark:border-slate-800'
                  }`}
                >
                  <span className="mb-1 block text-2xl">{g === 'male' ? '👨' : '👩'}</span>
                  {g === 'male' ? '男性' : '女性'}
                </button>
              ))}
            </div>
          </StepShell>
        )}

        {step === 1 && (
          <SliderStep
            icon="🎂"
            title="請設定您的年齡"
            hint="年齡影響基礎代謝率的估算"
            value={draft.age_years}
            unit="歲"
            min={1}
            max={100}
            step={1}
            onChange={(v) => patch({ age_years: v })}
          />
        )}

        {step === 2 && (
          <SliderStep
            icon="📏"
            title="請設定您的身高"
            hint="拖動滑桿調整"
            value={draft.height_cm}
            unit="cm"
            min={60}
            max={280}
            step={1}
            onChange={(v) => patch({ height_cm: v })}
          />
        )}

        {step === 3 && (
          <SliderStep
            icon="⚖️"
            title="請設定您的體重"
            hint="日後可於設定頁隨時更新"
            value={draft.weight_kg}
            unit="kg"
            min={30}
            max={120}
            step={0.5}
            onChange={(v) => patch({ weight_kg: v })}
          />
        )}

        {step === 4 && (
          <StepShell icon="🏃" title="請選擇日常活動量" hint="用於精算 TDEE 每日總熱量消耗">
            <div className="space-y-3">
              {ACTIVITY_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => patch({ activity_level: option.value })}
                  className={`flex w-full items-center gap-4 rounded-3xl border-2 p-4 text-left transition ${
                    draft.activity_level === option.value
                      ? 'border-brand-500 bg-brand-50/60 dark:bg-brand-950/40'
                      : 'border-slate-200 dark:border-slate-800'
                  }`}
                >
                  <span className="text-2xl">{option.icon}</span>
                  <span className="flex-1">
                    <span className="flex items-center justify-between">
                      <span className="text-xs font-bold">{option.label}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500 dark:bg-slate-800">
                        {option.freq}
                      </span>
                    </span>
                    <span className="mt-1 block text-[11px] leading-tight text-slate-500">
                      {option.detail}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </StepShell>
        )}

        {step === 5 && result && <TargetsSummary profile={result} />}
      </div>

      <footer className="space-y-3">
        {mutation.isError && (
          <p role="alert" className="text-center text-xs font-semibold text-rose-600">
            儲存失敗，請確認輸入後再試一次。
          </p>
        )}

        {step < 5 ? (
          <button
            type="button"
            onClick={next}
            disabled={mutation.isPending}
            className="w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-4 text-sm font-black text-white shadow-lg transition active:scale-95 disabled:opacity-60"
          >
            {mutation.isPending ? '計算中…' : step === 4 ? '完成並計算' : '下一步'}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => router.replace('/dashboard')}
            className="w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-4 text-sm font-black text-white shadow-lg transition active:scale-95"
          >
            開始使用
          </button>
        )}
      </footer>
    </main>
  )
}

function StepShell({
  icon,
  title,
  hint,
  children,
}: {
  icon: string
  title: string
  hint: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-5">
      <div className="space-y-1 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-brand-100 text-2xl dark:bg-brand-950/80">
          {icon}
        </div>
        <h2 className="text-xl font-black">{title}</h2>
        <p className="text-xs text-slate-400">{hint}</p>
      </div>
      {children}
    </section>
  )
}

function SliderStep({
  icon,
  title,
  hint,
  value,
  unit,
  min,
  max,
  step,
  onChange,
}: {
  icon: string
  title: string
  hint: string
  value: number
  unit: string
  min: number
  max: number
  step: number
  onChange: (value: number) => void
}) {
  return (
    <StepShell icon={icon} title={title} hint={hint}>
      <div className="space-y-4">
        <p className="numeric-stable text-center text-4xl font-black text-brand-600 dark:text-brand-400">
          {value}
          <span className="ml-1 text-base font-medium text-slate-400">{unit}</span>
        </p>
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          aria-label={title}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-brand-500 dark:bg-slate-800"
        />
      </div>
    </StepShell>
  )
}

/** TDEE 結果頁（T064）。數值全部來自後端，前端不重算。 */
function TargetsSummary({ profile }: { profile: HealthProfile }) {
  return (
    <section className="space-y-5 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-tr from-brand-600 to-emerald-400 text-2xl text-white shadow-xl">
        ✨
      </div>
      <div className="space-y-1">
        <h2 className="text-xl font-black">TDEE / BMR 計算完成！</h2>
        <p className="text-xs text-slate-400">已為您估算每日熱量與營養素目標：</p>
      </div>

      <div className="mx-auto max-w-xs space-y-3 rounded-3xl border border-slate-200/80 bg-white p-4 text-left dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 dark:border-slate-800">
          <span className="text-xs font-semibold text-slate-500">每日建議總熱量 (TDEE)</span>
          <span className="numeric-stable text-lg font-black text-brand-600 dark:text-brand-400">
            {Math.round(profile.tdee_kcal).toLocaleString()} kcal
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <MacroCell label="蛋白質" value={profile.target_protein_g} className="text-indigo-500" />
          <MacroCell label="碳水化合物" value={profile.target_carbs_g} className="text-amber-500" />
          <MacroCell label="脂肪" value={profile.target_fat_g} className="text-rose-500" />
        </div>
        <p className="pt-1 text-[10px] leading-relaxed text-slate-400">
          以上為估算參考值，非醫療診斷或治療建議。
        </p>
      </div>
    </section>
  )
}

function MacroCell({
  label,
  value,
  className,
}: {
  label: string
  value: number
  className: string
}) {
  return (
    <div className="rounded-2xl bg-slate-50 p-2.5 dark:bg-slate-800/60">
      <div className={`text-[10px] font-bold ${className}`}>{label}</div>
      <div className="numeric-stable mt-0.5 font-black">{Math.round(value)}g</div>
    </div>
  )
}
