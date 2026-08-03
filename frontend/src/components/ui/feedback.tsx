'use client'

/**
 * 統一的載入、空狀態與骨架元件（T115）。
 *
 * 先前各頁各自實作 spinner 與空狀態，樣式與無障礙標註都不一致。
 * 收斂到這裡後，`role="status"` 與 `aria-live` 只需要對一次。
 */

import Link from 'next/link'

export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const dimension = { sm: 'h-6 w-6 border-2', md: 'h-10 w-10 border-4', lg: 'h-14 w-14 border-4' }[
    size
  ]
  return (
    <div
      className={`${dimension} animate-spin rounded-full border-slate-200 border-t-brand-500 dark:border-slate-800 dark:border-t-brand-400`}
    />
  )
}

/** 頁面級載入狀態。 */
export function PageLoading({ label = '載入中…' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[60dvh] flex-col items-center justify-center gap-3"
    >
      <Spinner />
      <span className="sr-only">{label}</span>
    </div>
  )
}

/** 統一空狀態：圖示 + 標題 + 說明 + 可選的行動按鈕。 */
export function EmptyState({
  icon,
  title,
  description,
  actionHref,
  actionLabel,
  onAction,
  dashed = true,
}: {
  icon: string
  title: string
  description?: string
  actionHref?: string
  actionLabel?: string
  onAction?: () => void
  dashed?: boolean
}) {
  const action = actionLabel ? (
    actionHref ? (
      <Link
        href={actionHref}
        className="mt-3 inline-block rounded-xl bg-brand-500 px-4 py-2 text-xs font-bold text-white shadow-brand-glow transition active:scale-95"
      >
        {actionLabel}
      </Link>
    ) : (
      <button
        type="button"
        onClick={onAction}
        className="mt-3 rounded-xl bg-brand-500 px-4 py-2 text-xs font-bold text-white shadow-brand-glow transition active:scale-95"
      >
        {actionLabel}
      </button>
    )
  ) : null

  return (
    <div
      className={`rounded-3xl px-4 py-8 text-center ${
        dashed ? 'border border-dashed border-slate-300 dark:border-slate-700' : ''
      }`}
    >
      <p className="text-2xl" aria-hidden>
        {icon}
      </p>
      <p className="mt-2 text-sm font-black">{title}</p>
      {description && <p className="mt-1 text-xs text-slate-400">{description}</p>}
      {action}
    </div>
  )
}

/** 內容載入骨架，避免版面在資料到達時跳動。 */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`relative overflow-hidden rounded-2xl bg-slate-200 dark:bg-slate-800 ${className}`}
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent dark:via-white/10" />
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-4 px-4 py-4" role="status" aria-live="polite">
      <span className="sr-only">儀表板載入中</span>
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-44 w-full rounded-3xl" />
      <div className="grid grid-cols-3 gap-2.5">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-28 w-full rounded-3xl" />
    </div>
  )
}
