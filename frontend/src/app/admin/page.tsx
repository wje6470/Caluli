'use client'

/**
 * 後台首頁。
 *
 * US1（本階段）只確認權限邊界成立，後台尚無功能。
 * 店家清單與 CRUD 於 US2（tasks.md T023）取代此頁內容。
 */

export default function AdminHomePage() {
  return (
    <div className="rounded border border-slate-200 bg-white p-6">
      <p className="text-slate-700">後台已就緒。</p>
      <p className="mt-2 text-sm text-slate-500">
        店家與餐點維護功能尚未啟用，將於下一階段加入。
      </p>
    </div>
  )
}
