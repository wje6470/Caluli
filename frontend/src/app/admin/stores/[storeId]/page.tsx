'use client'

/**
 * 店家餐點維護（spec US3）。
 *
 * ★ 呈現上唯一要小心的地方：null 與 0 是兩件事
 * ============================================
 * null（店家未提供）顯示為「未提供」，0（確實為零）顯示為 0。
 * 用 `value || '—'` 這種寫法會把 0 也當成假值而顯示成「—」，正是 FR-033
 * 禁止的行為，故一律以 `=== null` 明確判斷。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/admin/ConfirmDialog'
import { MenuItemForm } from '@/components/admin/MenuItemForm'
import { ApiError } from '@/lib/api/client'
import { adminApi } from '@/lib/api/endpoints'
import type { MenuItem, MenuItemInput } from '@/lib/api/types'

/** null → 「未提供」；0 → 「0」。不可用 falsy 判斷（FR-033）。 */
function NutritionCell({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-xs text-slate-400">未提供</span>
  }
  return <span>{value}</span>
}

export default function AdminStoreMenuPage() {
  const params = useParams<{ storeId: string }>()
  const storeId = params.storeId
  const queryClient = useQueryClient()

  const [editing, setEditing] = useState<MenuItem | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<MenuItem | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const menuKey = ['admin', 'stores', storeId, 'menu-items']

  const store = useQuery({
    queryKey: ['admin', 'stores', storeId],
    queryFn: () => adminApi.stores.get(storeId),
  })

  const menu = useQuery({
    queryKey: menuKey,
    queryFn: () => adminApi.menuItems.list(storeId),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: menuKey })
  const asMessage = (err: unknown) =>
    err instanceof ApiError ? err.message : '操作失敗，請稍後再試。'

  const save = useMutation({
    mutationFn: (input: MenuItemInput) =>
      editing
        ? adminApi.menuItems.update(editing.id, input)
        : adminApi.menuItems.create(storeId, input),
    onSuccess: async () => {
      await invalidate()
      setEditing(undefined)
      setFormError(null)
    },
    onError: (err) => setFormError(asMessage(err)),
  })

  const remove = useMutation({
    mutationFn: (id: string) => adminApi.menuItems.remove(id),
    onSuccess: async () => {
      await invalidate()
      setDeleting(null)
    },
  })

  const backLink = (
    <Link href="/admin" className="text-sm text-slate-600 underline underline-offset-2">
      ← 回店家清單
    </Link>
  )

  if (store.isError || menu.isError) {
    return (
      <div className="space-y-4">
        {backLink}
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {asMessage(store.error ?? menu.error)}
        </p>
      </div>
    )
  }

  if (store.isPending || menu.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
        <p className="text-sm text-slate-500">載入中…</p>
      </div>
    )
  }

  const items = menu.data.menu_items

  return (
    <div className="space-y-4">
      {backLink}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">{store.data.name}</h2>
          <p className="text-sm text-slate-500">
            {store.data.address} · 共 {items.length} 道餐點
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditing(null)
            setFormError(null)
          }}
          className="rounded bg-slate-800 px-4 py-2 text-sm text-white"
        >
          新增餐點
        </button>
      </div>

      {items.length === 0 ? (
        // FR-036：尚無餐點是正常狀態，要有說明與下一步，不是空白或錯誤。
        <div className="rounded border border-slate-200 bg-white p-8 text-center">
          <p className="text-slate-700">這家店還沒有任何餐點。</p>
          <p className="mt-1 text-sm text-slate-500">點擊右上角「新增餐點」開始建檔。</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-2 font-medium">餐點名稱</th>
                <th className="px-4 py-2 font-medium">熱量</th>
                <th className="px-4 py-2 font-medium">蛋白質</th>
                <th className="px-4 py-2 font-medium">碳水</th>
                <th className="px-4 py-2 font-medium">脂肪</th>
                <th className="px-4 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-900">{item.name}</td>
                  <td className="px-4 py-2 text-slate-600">
                    <NutritionCell value={item.calories} />
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    <NutritionCell value={item.protein_g} />
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    <NutritionCell value={item.carbs_g} />
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    <NutritionCell value={item.fat_g} />
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(item)
                          setFormError(null)
                        }}
                        className="text-slate-700 underline underline-offset-2"
                      >
                        編輯
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleting(item)}
                        className="text-red-600 underline underline-offset-2"
                      >
                        刪除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-slate-500">
        標示「未提供」的欄位代表店家未提供該項數值，與數值 0 意義不同——使用者端會分別顯示為
        「無資料」與「0」。
      </p>

      {editing !== undefined && (
        <MenuItemForm
          item={editing}
          pending={save.isPending}
          error={formError}
          onCancel={() => {
            setEditing(undefined)
            setFormError(null)
          }}
          onSubmit={(input) => save.mutate(input)}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="刪除餐點"
          message={`確定要刪除「${deleting.name}」嗎？`}
          consequence="只會刪除這道餐點，店家與其他餐點不受影響。"
          confirmLabel="確定刪除"
          pending={remove.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => remove.mutate(deleting.id)}
        />
      )}
    </div>
  )
}
