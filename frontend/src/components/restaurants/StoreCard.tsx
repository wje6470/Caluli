'use client'

/**
 * 店家清單的單一項目。
 *
 * ⚠️ 地址是**必要欄位而非裝飾**（FR-016）：店名不具唯一性，連鎖分店同名是
 * 正常資料，缺少地址時使用者無法辨別這是哪一家分店。
 *
 * ⚠️ 連結一律以 `id` 組成，不得以 `name`（FR-016a）。
 */

import Link from 'next/link'

import { formatDistance } from '@/lib/format/distance'
import type { Store } from '@/lib/api/types'

export function StoreCard({ store }: { store: Store }) {
  return (
    <Link
      href={`/restaurants/${store.id}`}
      className="block rounded-2xl border border-slate-200/80 bg-white px-4 py-3 transition active:scale-[0.99] hover:border-brand-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-brand-700"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-bold">{store.name}</h3>
          {/* 同名分店靠這行區分——不可省略。 */}
          <p className="mt-0.5 truncate text-[11px] text-slate-400">
            {store.address ?? '地址未提供'}
          </p>
        </div>

        {/* distance_m 為 null 代表「未計算」（全部模式），不顯示距離欄位，
            而不是顯示 0 公尺。 */}
        {store.distance_m !== null && (
          <span className="numeric-stable shrink-0 rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-black text-brand-600 dark:bg-brand-950/60 dark:text-brand-400">
            {formatDistance(store.distance_m)}
          </span>
        )}
      </div>
    </Link>
  )
}
