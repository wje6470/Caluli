'use client'

/**
 * 權限／狀態說明的共用呈現元件。
 *
 * research.md R-02 的評估結論：第一輪的相機權限與本輪的定位權限，
 * **取得機制無共同抽象**（file input vs geolocation API，前者甚至偵測不到
 * 拒絕），強行統一只會產出一個空洞的介面；但**呈現層可以共用**——兩者的
 * 「被拒畫面」視覺結構相同。
 *
 * 故本元件只負責呈現：圖示 ＋ 標題 ＋ 說明 ＋ 主要動作 ＋ 次要動作。
 *
 * 第一輪的 capture/page.tsx 改用此元件屬**可選後續改善，不在本輪範圍**——
 * 已驗收的流程不為形式一致而承擔回歸風險。
 */

import type { ReactNode } from 'react'

export function PermissionNotice({
  icon,
  title,
  description,
  hint,
  primaryAction,
  secondaryAction,
  tone = 'neutral',
}: {
  icon: string
  title: string
  description: ReactNode
  hint?: ReactNode
  primaryAction?: { label: string; onClick: () => void }
  secondaryAction?: { label: string; onClick: () => void }
  tone?: 'neutral' | 'warning'
}) {
  const iconBg =
    tone === 'warning'
      ? 'bg-amber-50 dark:bg-amber-950/40'
      : 'bg-slate-100 dark:bg-slate-800'

  return (
    <section
      role="status"
      className="flex flex-col items-center gap-3 rounded-3xl border border-slate-200/80 px-5 py-6 text-center dark:border-slate-800"
    >
      <div className={`flex h-14 w-14 items-center justify-center rounded-3xl text-3xl ${iconBg}`}>
        <span aria-hidden>{icon}</span>
      </div>

      <div className="space-y-1">
        <h2 className="text-sm font-black">{title}</h2>
        <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">{description}</p>
        {hint && <p className="pt-0.5 text-[11px] leading-relaxed text-slate-400">{hint}</p>}
      </div>

      {(primaryAction || secondaryAction) && (
        <div className="flex w-full max-w-xs flex-col gap-2 pt-1">
          {primaryAction && (
            <button
              type="button"
              onClick={primaryAction.onClick}
              className="w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-3 text-sm font-black text-white shadow-lg transition active:scale-95"
            >
              {primaryAction.label}
            </button>
          )}
          {secondaryAction && (
            <button
              type="button"
              onClick={secondaryAction.onClick}
              className="w-full rounded-2xl border border-slate-200 py-2.5 text-xs font-bold transition active:scale-95 dark:border-slate-700"
            >
              {secondaryAction.label}
            </button>
          )}
        </div>
      )}
    </section>
  )
}
