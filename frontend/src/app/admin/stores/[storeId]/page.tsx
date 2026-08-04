'use client'

/**
 * 店家餐點維護。
 *
 * US2 階段先放此佔位頁，讓店家清單的「餐點」連結有去處而非 404；
 * US3（tasks.md T032）以實際的餐點清單與 CRUD 取代本頁內容。
 */

import Link from 'next/link'

export default function AdminStoreMenuPage() {
  return (
    <div className="space-y-4">
      <Link href="/admin" className="text-sm text-slate-600 underline underline-offset-2">
        ← 回店家清單
      </Link>
      <div className="rounded border border-slate-200 bg-white p-8 text-center">
        <p className="text-slate-700">餐點維護功能尚未啟用。</p>
        <p className="mt-1 text-sm text-slate-500">將於下一階段加入。</p>
      </div>
    </div>
  )
}
