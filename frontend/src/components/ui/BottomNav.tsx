'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const TABS = [
  { href: '/dashboard', label: '首頁', icon: '🏠' },
  { href: '/capture', label: '拍照記帳', icon: '📷' },
  { href: '/trends', label: '趨勢', icon: '📈' },
  { href: '/profile', label: '我的', icon: '👤' },
] as const

export function BottomNav() {
  const pathname = usePathname()

  return (
    <nav
      aria-label="主要導覽"
      className="fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-md border-t border-slate-200/80 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95"
    >
      <ul className="flex">
        {TABS.map((tab) => {
          const active = pathname === tab.href
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
