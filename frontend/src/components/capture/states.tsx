'use client'

/** 辨識流程的 Loading / 空結果 / 錯誤三種畫面。 */

import type { ApiError } from '@/lib/api/client'

/** T076：辨識期間全程顯示（FR-025）。 */
export function LoadingState() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[60dvh] flex-col items-center justify-center gap-4 px-6 text-center"
    >
      <div className="h-14 w-14 animate-spin rounded-full border-4 border-slate-200 border-t-brand-500 dark:border-slate-800 dark:border-t-brand-400" />
      <div>
        <p className="text-sm font-black">AI 分析中…</p>
        <p className="mt-1 text-xs text-slate-400">正在辨識餐點並估算營養素，請稍候</p>
      </div>
    </div>
  )
}

/**
 * ★ T084 / FR-027：未偵測到食物的專屬引導畫面。
 *
 * 這是**成功**的辨識結果，不是錯誤——所以畫面語氣是引導而非報錯，
 * 且**絕不**渲染空的結果清單。
 */
export function EmptyResultGuide({
  message,
  onRetake,
  onBack,
}: {
  message: string | null
  onRetake: () => void
  onBack: () => void
}) {
  return (
    <div className="flex min-h-[60dvh] flex-col items-center justify-center gap-5 px-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-3xl dark:bg-slate-800">
        🔍
      </div>
      <div className="space-y-1">
        <h2 className="text-base font-black">沒有辨識到食物</h2>
        {/* 原樣顯示辨識服務回傳的訊息。 */}
        <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          {message ?? '沒有偵測到食物，請換一張再試試'}
        </p>
        <p className="pt-1 text-[11px] text-slate-400">
          小提示：讓餐點填滿畫面、避免過暗或反光，辨識會更準確。
        </p>
      </div>
      <div className="flex w-full max-w-xs flex-col gap-2">
        <button
          type="button"
          onClick={onRetake}
          className="w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-3.5 text-sm font-black text-white shadow-lg transition active:scale-95"
        >
          重新拍攝
        </button>
        <button
          type="button"
          onClick={onBack}
          className="w-full rounded-2xl py-3 text-sm font-bold text-slate-500 transition hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          返回
        </button>
      </div>
    </div>
  )
}

/**
 * T085 / FR-028、FR-029：錯誤畫面。
 *
 * 「重試」依 error.retryable 決定是否顯示——前端不自行維護 code 對照表。
 * 重試**不需重新選取照片**（後端重用已存檔的照片）。
 */
export function ErrorState({
  error,
  failureCount,
  canRetry,
  onRetry,
  onRetake,
  onBack,
}: {
  error: ApiError | null
  failureCount: number
  canRetry: boolean
  onRetry: () => void
  onRetake: () => void
  onBack: () => void
}) {
  const retryable = error?.retryable ?? true
  // 連續 3 次失敗後另外提供返回出口，避免使用者卡在錯誤狀態。
  const showEscape = failureCount >= 3

  return (
    <div
      role="alert"
      className="flex min-h-[60dvh] flex-col items-center justify-center gap-5 px-6 text-center"
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-rose-50 text-3xl dark:bg-rose-950/40">
        ⚠️
      </div>
      <div className="space-y-1">
        <h2 className="text-base font-black">辨識沒有完成</h2>
        <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          {error?.message ?? '系統發生問題，請稍後再試。'}
        </p>
        {showEscape && (
          <p className="pt-1 text-[11px] text-slate-400">
            已連續失敗 {failureCount} 次，您可以稍後再回來試試。
          </p>
        )}
      </div>

      <div className="flex w-full max-w-xs flex-col gap-2">
        {retryable && canRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-3.5 text-sm font-black text-white shadow-lg transition active:scale-95"
          >
            重試（不需重新拍照）
          </button>
        )}
        <button
          type="button"
          onClick={onRetake}
          className="w-full rounded-2xl border border-slate-200 py-3 text-sm font-bold transition active:scale-95 dark:border-slate-700"
        >
          重新拍攝
        </button>
        {showEscape && (
          <button
            type="button"
            onClick={onBack}
            className="w-full rounded-2xl py-3 text-sm font-bold text-slate-500 transition hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            返回首頁
          </button>
        )}
      </div>
    </div>
  )
}
