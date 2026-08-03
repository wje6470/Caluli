'use client'

/** 個人設定（US5，T106）+ 深色模式切換（T112）。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { PageLoading } from '@/components/ui/feedback'
import { tokenStore } from '@/lib/api/client'
import { profileApi } from '@/lib/api/endpoints'
import type { ActivityLevel, Gender, HealthProfileInput } from '@/lib/api/types'
import { formatKcal } from '@/lib/nutrition'

const THEME_KEY = 'caluli.theme'

const ACTIVITY_LABELS: Record<ActivityLevel, string> = {
  low: '低活動量',
  moderate: '中活動量',
  high: '高活動量',
}

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const { data, isPending } = useQuery({ queryKey: ['me'], queryFn: profileApi.me })
  const [editing, setEditing] = useState(false)
  const [dark, setDark] = useState(false)

  useEffect(() => {
    setDark(document.documentElement.classList.contains('dark'))
  }, [])

  const toggleTheme = () => {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle('dark', next)
    window.localStorage.setItem(THEME_KEY, next ? 'dark' : 'light')
  }

  if (isPending || !data?.profile) {
    return <PageLoading label="個人資料載入中" />
  }

  const profile = data.profile

  return (
    <main className="space-y-5 px-4 py-4">
      <section className="flex items-center gap-4 rounded-3xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-tr from-brand-600 to-emerald-400 text-2xl text-white">
          {data.user.display_name?.slice(0, 1) ?? '👤'}
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-base font-extrabold">{data.user.display_name ?? '使用者'}</h1>
          <span className="mt-1 inline-block rounded-full border border-brand-200 bg-brand-50 px-2.5 py-0.5 text-[11px] font-semibold text-brand-600 dark:border-brand-800/60 dark:bg-brand-950/80 dark:text-brand-400">
            以 LINE 帳號登入
          </span>
        </div>
      </section>

      <section>
        <h2 className="mb-2.5 px-1 text-xs font-bold uppercase tracking-wider text-slate-400">
          身體基本數據
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <Stat label="身高" value={`${profile.height_cm}`} unit="cm" />
          <Stat label="體重" value={`${profile.weight_kg}`} unit="kg" />
          <Stat
            label="年齡 / 性別"
            value={`${profile.age_years} 歲`}
            unit={profile.gender === 'male' ? '(男性)' : '(女性)'}
          />
          <Stat label="每日活動量" value={ACTIVITY_LABELS[profile.activity_level]} unit="" />
        </div>
      </section>

      <section className="space-y-3 rounded-3xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          每日營養目標 (TDEE/BMR)
        </h2>
        <Row label="基礎代謝率 (BMR)" value={`${formatKcal(profile.bmr_kcal)} kcal`} />
        <Row label="每日建議總熱量" value={`${formatKcal(profile.tdee_kcal)} kcal`} />
        <Row label="蛋白質目標" value={`${Math.round(profile.target_protein_g)} g`} accent="text-indigo-500" />
        <Row label="碳水化合物目標" value={`${Math.round(profile.target_carbs_g)} g`} accent="text-amber-500" />
        <Row label="脂肪目標" value={`${Math.round(profile.target_fat_g)} g`} accent="text-rose-500" last />
      </section>

      <section className="space-y-2">
        <h2 className="px-1 text-xs font-bold uppercase tracking-wider text-slate-400">
          偏好與帳號設定
        </h2>
        <div className="divide-y divide-slate-100 overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-sm dark:divide-slate-800/60 dark:border-slate-800 dark:bg-slate-900">
          <button
            type="button"
            onClick={toggleTheme}
            className="flex w-full items-center justify-between p-4 transition hover:bg-slate-50 dark:hover:bg-slate-800/40"
          >
            <span className="text-left">
              <span className="block text-xs font-bold">深色模式</span>
              <span className="text-[10px] text-slate-400">
                目前：{dark ? '深色主題' : '淺色主題'}
              </span>
            </span>
            <span
              aria-hidden
              className={`h-5 w-9 rounded-full transition ${dark ? 'bg-brand-500' : 'bg-slate-200 dark:bg-slate-700'}`}
            >
              <span
                className={`block h-4 w-4 translate-y-[2px] rounded-full bg-white transition ${dark ? 'translate-x-[18px]' : 'translate-x-[2px]'}`}
              />
            </span>
          </button>

          <button
            type="button"
            onClick={() => setEditing(true)}
            className="flex w-full items-center justify-between p-4 transition hover:bg-slate-50 dark:hover:bg-slate-800/40"
          >
            <span className="text-left">
              <span className="block text-xs font-bold">修改個人資訊</span>
              <span className="text-[10px] text-slate-400">重新計算 TDEE 與營養目標</span>
            </span>
            <span className="text-xs text-slate-400">›</span>
          </button>

          <button
            type="button"
            onClick={() => {
              tokenStore.clear()
              window.location.href = '/login'
            }}
            className="flex w-full items-center p-4 text-xs font-bold text-rose-500 transition hover:bg-rose-50 dark:hover:bg-rose-950/40"
          >
            登出
          </button>
        </div>
      </section>

      <p className="pb-2 text-center text-[10px] leading-relaxed text-slate-400">
        本服務僅提供熱量與營養素估算參考，不提供醫療診斷或治療建議。
      </p>

      {editing && (
        <ProfileEditSheet
          initial={{
            gender: profile.gender as Gender,
            age_years: profile.age_years,
            height_cm: profile.height_cm,
            weight_kg: profile.weight_kg,
            activity_level: profile.activity_level as ActivityLevel,
          }}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            // 目標值變動 → 儀表板與趨勢的達成率須重新取得。
            queryClient.invalidateQueries({ queryKey: ['me'] })
            queryClient.invalidateQueries({ queryKey: ['dashboard'] })
            queryClient.invalidateQueries({ queryKey: ['trends'] })
          }}
        />
      )}
    </main>
  )
}

function Stat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-3.5 dark:border-slate-800 dark:bg-slate-900">
      <span className="text-xs font-semibold text-slate-400">{label}</span>
      <div className="numeric-stable mt-0.5 text-base font-black">
        {value} <span className="text-xs font-normal text-slate-400">{unit}</span>
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  accent,
  last,
}: {
  label: string
  value: string
  accent?: string
  last?: boolean
}) {
  return (
    <div
      className={`flex items-center justify-between py-1.5 ${
        last ? '' : 'border-b border-slate-100 dark:border-slate-800/60'
      }`}
    >
      <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">{label}</span>
      <span className={`numeric-stable text-xs font-black ${accent ?? ''}`}>{value}</span>
    </div>
  )
}

/** 修改個人資訊 → 後端重算目標（FR-015）。歷史紀錄不受影響（FR-016）。 */
function ProfileEditSheet({
  initial,
  onClose,
  onSaved,
}: {
  initial: HealthProfileInput
  onClose: () => void
  onSaved: () => void
}) {
  const [draft, setDraft] = useState<HealthProfileInput>(initial)

  const save = useMutation({
    mutationFn: () => profileApi.upsert(draft),
    onSuccess: onSaved,
  })

  const fields = [
    { key: 'age_years', label: '年齡', unit: '歲', min: 15, max: 90, step: 1 },
    { key: 'height_cm', label: '身高', unit: 'cm', min: 100, max: 250, step: 1 },
    { key: 'weight_kg', label: '體重', unit: 'kg', min: 25, max: 300, step: 0.5 },
  ] as const

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/60 backdrop-blur-sm">
      <div className="max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-slate-50 p-5 dark:bg-slate-950">
        <header className="mb-4 flex items-center justify-between">
          <button type="button" onClick={onClose} className="text-xs font-bold text-slate-400">
            取消
          </button>
          <h2 className="text-sm font-black">修改個人資訊</h2>
          <span className="w-8" />
        </header>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {(['male', 'female'] as const).map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setDraft((d) => ({ ...d, gender: g }))}
                className={`rounded-2xl border-2 py-3 text-xs font-bold transition ${
                  draft.gender === g
                    ? 'border-brand-500 bg-brand-50/60 dark:bg-brand-950/40'
                    : 'border-slate-200 dark:border-slate-800'
                }`}
              >
                {g === 'male' ? '男性' : '女性'}
              </button>
            ))}
          </div>

          {fields.map((field) => (
            <div key={field.key}>
              <div className="mb-1 flex items-baseline justify-between">
                <label htmlFor={field.key} className="text-[11px] font-bold uppercase text-slate-400">
                  {field.label}
                </label>
                <span className="numeric-stable text-sm font-black text-brand-600 dark:text-brand-400">
                  {draft[field.key]} {field.unit}
                </span>
              </div>
              <input
                id={field.key}
                type="range"
                min={field.min}
                max={field.max}
                step={field.step}
                value={draft[field.key]}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, [field.key]: Number(e.target.value) }))
                }
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-brand-500 dark:bg-slate-800"
              />
            </div>
          ))}

          <div>
            <span className="mb-1 block text-[11px] font-bold uppercase text-slate-400">活動量</span>
            <div className="grid grid-cols-3 gap-2">
              {(['low', 'moderate', 'high'] as const).map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setDraft((d) => ({ ...d, activity_level: level }))}
                  className={`rounded-2xl border-2 py-2.5 text-[11px] font-bold transition ${
                    draft.activity_level === level
                      ? 'border-brand-500 bg-brand-50/60 dark:bg-brand-950/40'
                      : 'border-slate-200 dark:border-slate-800'
                  }`}
                >
                  {ACTIVITY_LABELS[level]}
                </button>
              ))}
            </div>
          </div>
        </div>

        {save.isError && (
          <p role="alert" className="mt-3 text-center text-xs font-semibold text-rose-600">
            儲存失敗，請檢查輸入後再試。
          </p>
        )}

        <p className="mt-3 text-center text-[10px] text-slate-400">
          修改後會重新計算每日目標，過去的飲食紀錄不會被改變。
        </p>

        <button
          type="button"
          disabled={save.isPending}
          onClick={() => save.mutate()}
          className="mt-3 w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-4 text-sm font-black text-white shadow-lg transition active:scale-95 disabled:opacity-50"
        >
          {save.isPending ? '重新計算中…' : '儲存並重新計算'}
        </button>
      </div>
    </div>
  )
}
