'use client'

/**
 * 共用 Modal / Sheet（T114）。
 *
 * 除了動畫節奏統一，也集中處理無障礙要件（T119）：
 * Escape 關閉、背景滾動鎖定、焦點移入、role/aria 標註。
 * 這些若讓各處自行實作，一定會有地方漏掉。
 */

import { useEffect, useRef } from 'react'

type Props = {
  title: string
  onClose: () => void
  children: React.ReactNode
  /** sheet：由下滑入（行動優先）；center：置中縮放。 */
  variant?: 'sheet' | 'center'
  footer?: React.ReactNode
}

export function Modal({ title, onClose, children, variant = 'sheet', footer }: Props) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)

    // 開啟期間鎖住背景滾動，避免行動裝置上的滾動穿透。
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    panelRef.current?.focus()

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [onClose])

  const isSheet = variant === 'sheet'

  return (
    <div
      className={`fixed inset-0 z-50 flex animate-fade-in justify-center bg-slate-950/60 backdrop-blur-sm ${
        isSheet ? 'items-end' : 'items-center p-4'
      }`}
      onClick={(event) => {
        // 只在點擊遮罩本身時關閉，點內容不關。
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`w-full max-w-md overflow-y-auto bg-slate-50 outline-none dark:bg-slate-950 ${
          isSheet
            ? 'max-h-[90dvh] animate-sheet-up rounded-t-3xl p-5'
            : 'max-h-[85dvh] animate-scale-in rounded-3xl p-5 shadow-hero'
        }`}
      >
        <header className="mb-4 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-1 text-xs font-bold text-slate-400 transition hover:text-slate-600 focus-visible:ring-2 focus-visible:ring-brand-500 dark:hover:text-slate-200"
          >
            取消
          </button>
          <h2 className="text-sm font-black">{title}</h2>
          <span className="w-8" aria-hidden />
        </header>

        {children}

        {footer && <div className="mt-4">{footer}</div>}
      </div>
    </div>
  )
}
