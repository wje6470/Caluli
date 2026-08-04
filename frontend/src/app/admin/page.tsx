'use client'

/**
 * 後台店家清單與維護（spec US2）。
 *
 * 介面以精簡為原則（FR-045、FR-046）：原生 table + form，不引入元件庫、
 * 不比照產品原型的視覺風格、不做深色模式。重點在寫入正確性。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/admin/ConfirmDialog'
import { StoreForm } from '@/components/admin/StoreForm'
import { ApiError } from '@/lib/api/client'
import { adminApi } from '@/lib/api/endpoints'
import type { Store, StoreInput, StoreWithCount } from '@/lib/api/types'

const STORES_KEY = ['admin', 'stores']

export default function AdminStoresPage() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Store | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<StoreWithCount | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const { data, isPending, isError, error } = useQuery({
    queryKey: STORES_KEY,
    queryFn: adminApi.stores.list,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: STORES_KEY })
  const asMessage = (err: unknown) =>
    err instanceof ApiError ? err.message : '儲存失敗，請稍後再試。'

  const save = useMutation({
    mutationFn: (input: StoreInput) =>
      editing ? adminApi.stores.update(editing.id, input) : adminApi.stores.create(input),
    onSuccess: async () => {
      await invalidate()
      setEditing(undefined)
      setFormError(null)
    },
    onError: (err) => setFormError(asMessage(err)),
  })

  const remove = useMutation({
    mutationFn: (id: string) => adminApi.stores.remove(id),
    onSuccess: async () => {
      await invalidate()
      setDeleting(null)
    },
  })

  if (isPending) {
    return <p className="text-sm text-slate-500">載入中…</p>
  }

  if (isError) {
    return (
      <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {asMessage(error)}
      </p>
    )
  }

  const stores = data.stores
  const missingCoordinates = stores.filter((s) => s.latitude === null).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">店家</h2>
          <p className="text-sm text-slate-500">
            共 {stores.length} 家
            {/* FR-025：未設座標的店家要能一眼看出，不必逐家點開。 */}
            {missingCoordinates > 0 && (
              <span className="ml-2 text-amber-700">（{missingCoordinates} 家未設定座標）</span>
            )}
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
          新增店家
        </button>
      </div>

      {stores.length === 0 ? (
        <div className="rounded border border-slate-200 bg-white p-8 text-center">
          <p className="text-slate-700">尚未建立任何店家。</p>
          <p className="mt-1 text-sm text-slate-500">
            點擊右上角「新增店家」開始建檔。
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-2 font-medium">名稱</th>
                <th className="px-4 py-2 font-medium">地址</th>
                <th className="px-4 py-2 font-medium">座標</th>
                <th className="px-4 py-2 font-medium">餐點</th>
                <th className="px-4 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {stores.map((store) => (
                <tr key={store.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-900">{store.name}</td>
                  <td className="px-4 py-2 text-slate-600">{store.address}</td>
                  <td className="px-4 py-2">
                    {store.latitude === null ? (
                      // FR-025：明確標示並說明後果，而非只留白。
                      <span
                        className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-900"
                        title="未設定座標的店家不會出現在使用者端的附近店家推薦中"
                      >
                        未設定
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500">
                        {store.latitude.toFixed(4)}, {store.longitude?.toFixed(4)}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{store.menu_item_count}</td>
                  <td className="px-4 py-2">
                    <div className="flex gap-3">
                      <Link
                        href={`/admin/stores/${store.id}`}
                        className="text-slate-700 underline underline-offset-2"
                      >
                        餐點
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(store)
                          setFormError(null)
                        }}
                        className="text-slate-700 underline underline-offset-2"
                      >
                        編輯
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleting(store)}
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

      {missingCoordinates > 0 && (
        <p className="text-xs text-slate-500">
          標示「未設定」的店家沒有經緯度，<strong>不會出現在使用者端的附近店家推薦中</strong>
          ；補上座標後即會納入。
        </p>
      )}

      {editing !== undefined && (
        <StoreForm
          store={editing}
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
          title="刪除店家"
          message={`確定要刪除「${deleting.name}」嗎？`}
          // FR-038：明確告知將一併刪除的餐點數；沒有餐點時也要講清楚。
          consequence={
            deleting.menu_item_count > 0
              ? `這家店底下的 ${deleting.menu_item_count} 道餐點會一併被刪除。`
              : '這家店底下沒有餐點，不會有其他資料被一併刪除。'
          }
          confirmLabel="確定刪除"
          pending={remove.isPending}
          // FR-039：取消時不發出任何請求，不產生任何資料變更。
          onCancel={() => setDeleting(null)}
          onConfirm={() => remove.mutate(deleting.id)}
        />
      )}
    </div>
  )
}
