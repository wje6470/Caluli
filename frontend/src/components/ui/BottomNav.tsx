'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'

import { initRuntimeEnv, isInLiff } from '@/lib/liff/environment'

const TABS = [
  { href: '/dashboard', label: '首頁', icon: '🏠' },
  { href: '/capture', label: '拍照記帳', icon: '📷' },
  { href: '/trends', label: '趨勢', icon: '📈' },
  { href: '/profile', label: '我的', icon: '👤' },
] as const

/**
 * 推薦餐廳（第二輪）**僅於 LIFF 入口提供**（FR-001〜FR-003）。
 * 一般網頁、iOS App、Android App 三個入口不呈現此入口。
 */
const LIFF_ONLY_TABS = [{ href: '/restaurants', label: '找餐廳', icon: '🍜' }] as const

export function BottomNav() {
  const pathname = usePathname()

  /**
   * ⚠️ 環境判定完成前一律視為「非 LIFF」（初值 false）。
   *
   * isInLiff() 是同步函式，但它依賴 initRuntimeEnv() 已完成——判定前回傳的
   * 是尚未解析的狀態。若在此樂觀顯示，一般網頁會短暫閃現「找餐廳」分頁後
   * 才消失，違反 FR-002。寧可晚一瞬間出現，不可閃現（research.md R-03）。
   */
  const [inLiff, setInLiff] = useState(false)
  useEffect(() => {
    let cancelled = false
    void initRuntimeEnv().then(() => {
      if (!cancelled) setInLiff(isInLiff())
    })
    return () => {
      cancelled = true
    }
  }, [])

  const tabs = inLiff ? [...TABS, ...LIFF_ONLY_TABS] : TABS

  return (
    <nav
      aria-label="主要導覽"
      className="fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-md border-t border-slate-200/80 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95"
    >
      <ul className="flex">
        {tabs.map((tab) => {
          const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`)
          return (
            <li key={tab.href} className="flex-1">
              <Link
                href={tab.href}
                aria-current={active ? 'page' : undefined}
                className={`flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-bold transition ${
                  active
                    ? 'text-brand-600 dark:text-brand-400'
                    : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
                }`}
              >
                <span aria-hidden className="text-lg leading-none">
                  {tab.icon}
                </span>
                {tab.label}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
