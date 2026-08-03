'use client'

/** 飲食趨勢（US4，T100–T103）。 */

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { EmptyState, Spinner } from '@/components/ui/feedback'
import { analyticsApi } from '@/lib/api/endpoints'
import type { MetricKey } from '@/lib/api/types'

const RANGES = [7, 14, 30] as const
const METRICS: { key: MetricKey; label: string; color: string; unit: string }[] = [
  { key: 'calories', label: '熱量', color: '#10b981', unit: 'kcal' },
  { key: 'protein', label: '蛋白質', color: '#6366f1', unit: 'g' },
  { key: 'carbs', label: '碳水化合物', color: '#f59e0b', unit: 'g' },
  { key: 'fat', label: '脂肪', color: '#f43f5e', unit: 'g' },
]

export default function TrendsPage() {
  const [range, setRange] = useState<(typeof RANGES)[number]>(7)
  const [metric, setMetric] = useState<MetricKey>('calories')

  const { data, isPending } = useQuery({
    queryKey: ['trends', range, metric],
    queryFn: () => analyticsApi.trends(range, metric),
  })

  const active = METRICS.find((m) => m.key === metric)!
  // 全部為 0 = 尚無任何紀錄，顯示引導而非空圖表（FR-055）。
  const hasData = Boolean(data?.points.some((point) => point.value > 0))

  return (
    <main className="space-y-5 px-4 py-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-black">飲食趨勢與分析</h1>
          <p className="text-xs text-slate-400">觀察熱量與營養素的長期變化</p>
        </div>
        <select
          value={range}
          aria-label="時間區間"
          onChange={(e) => setRange(Number(e.target.value) as (typeof RANGES)[number])}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold shadow-sm outline-none dark:border-slate-800 dark:bg-slate-900"
        >
          {RANGES.map((value) => (
            <option key={value} value={value}>
              近 {value} 天
            </option>
          ))}
        </select>
      </header>

      <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1">
        {METRICS.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => setMetric(option.key)}
            aria-pressed={metric === option.key}
            className={`shrink-0 rounded-xl px-3 py-1.5 text-xs font-bold transition ${
              metric === option.key
                ? 'bg-brand-500 text-white shadow-md'
                : 'border border-slate-200 bg-white text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="rounded-3xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        {isPending || !data ? (
          <div className="flex h-64 items-center justify-center">
            <Spinner size="sm" />
          </div>
        ) : !hasData ? (
          <div className="flex h-64 items-center justify-center">
            <EmptyState
              icon="📈"
              title="還沒有足夠的紀錄"
              description="建立第一筆飲食紀錄後即可看到趨勢"
              actionHref="/capture"
              actionLabel="拍照記帳"
              dashed={false}
            />
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value: string) => value.slice(5)}
                  tick={{ fontSize: 10, fill: '#94a3b8' }}
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <Tooltip
                  formatter={(value: number) => [`${Math.round(value)} ${active.unit}`, active.label]}
                  contentStyle={{ borderRadius: 12, fontSize: 12 }}
                />
                {data.target && (
                  <ReferenceLine
                    y={data.target}
                    stroke="#94a3b8"
                    strokeDasharray="4 4"
                    label={{ value: '目標', fontSize: 10, fill: '#94a3b8', position: 'right' }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={active.color}
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {data && (
        <div className="grid grid-cols-2 gap-3">
          <SummaryCard
            label={`平均每日${active.label}`}
            value={`${Math.round(data.average).toLocaleString()}`}
            unit={active.unit}
          />
          <SummaryCard
            label="目標達成率"
            value={`${Math.round(data.target_achievement_rate * 100)}`}
            unit="%"
            hint="達標 = 攝取落在目標的 90%–110%"
          />
        </div>
      )}
    </main>
  )
}

/** T102：摘要卡片。 */
function SummaryCard({
  label,
  value,
  unit,
  hint,
}: {
  label: string
  value: string
  unit: string
  hint?: string
}) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs font-semibold text-slate-400">{label}</div>
      <div className="numeric-stable mt-1 text-xl font-black">
        {value}
        <span className="ml-1 text-xs font-normal text-slate-400">{unit}</span>
      </div>
      {hint && <p className="mt-1.5 text-[10px] text-slate-400">{hint}</p>}
    </div>
  )
}
