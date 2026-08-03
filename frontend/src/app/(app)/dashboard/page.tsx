'use client'

/** 主儀表板（US3）。T097 + T107/T108 的編輯與刪除入口。 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'

import {
  CalorieHeroCard,
  DateStrip,
  MacroCards,
  MealList,
  ViewModeToggle,
  type ViewMode,
} from '@/components/dashboard'
import { MealEditSheet } from '@/components/dashboard/MealEditSheet'
import { DashboardSkeleton } from '@/components/ui/feedback'
import { analyticsApi, mealRecordApi } from '@/lib/api/endpoints'
import type { MealRecord } from '@/lib/api/types'

const todayIso = () => new Date().toISOString().slice(0, 10)

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const [date, setDate] = useState(todayIso)
  const [mode, setMode] = useState<ViewMode>('consumed')
  const [editing, setEditing] = useState<MealRecord | null>(null)

  const { data, isPending } = useQuery({
    queryKey: ['dashboard', date],
    queryFn: () => analyticsApi.dashboard(date),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    queryClient.invalidateQueries({ queryKey: ['trends'] })
  }

  const remove = useMutation({
    mutationFn: (record: MealRecord) => mealRecordApi.remove(record.id),
    onSuccess: invalidate,
  })

  if (isPending || !data) {
    return <DashboardSkeleton />
  }

  return (
    <main className="space-y-5 px-4 py-4">
      <DateStrip selected={date} onSelect={setDate} />

      <section className="space-y-3.5">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            {date === todayIso() ? '今日營養概況' : `${date} 營養概況`}
          </h2>
          <ViewModeToggle mode={mode} onChange={setMode} />
        </div>

        <CalorieHeroCard data={data} mode={mode} />
        <MacroCards
          consumed={data.consumed}
          targets={data.targets}
          remaining={data.remaining}
          mode={mode}
        />
      </section>

      <section className="space-y-3 pt-1">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">餐點記錄</h2>
          <Link href="/capture" className="text-xs font-bold text-brand-600 dark:text-brand-400">
            + 拍照記帳
          </Link>
        </div>

        <MealList
          records={data.records}
          onEdit={setEditing}
          onDelete={(record) => {
            if (window.confirm(`確定要刪除這筆紀錄嗎？此操作無法復原。`)) {
              remove.mutate(record)
            }
          }}
        />
      </section>

      <p className="pb-2 text-center text-[10px] leading-relaxed text-slate-400">
        數值為估算參考，非醫療診斷或治療建議。
      </p>

      {editing && (
        <MealEditSheet
          record={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            invalidate()
          }}
        />
      )}
    </main>
  )
}
