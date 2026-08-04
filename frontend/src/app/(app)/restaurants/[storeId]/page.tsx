'use client'

/**
 * 推薦餐廳 — 店家餐點瀏覽（US2）。
 *
 * ⚠️ 返回行為（FR-026、US2-4）：以 router.back() 回到清單，讓清單維持原本的
 *    排序與捲動位置，且**不重新請求定位權限**——座標由 useCurrentLocation 的
 *    query cache 承載，client-side 導覽時 cache 仍在（research.md R-10）。
 *
 * ⚠️ 營養數值一律來自 menu_items，與第一輪的通用食物營養對照表無任何連動；
 *    即使餐點名稱與某食物相同也不查詢該表（憲章原則 V、FR-031）。
 */

import { useQuery } from '@tanstack/react-query'
import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { MenuItemRow } from '@/components/restaurants/MenuItemRow'
import {
  LiffOnlyNotice,
  LoadingState,
  NoMenuItems,
  StoreNotFound,
} from '@/components/restaurants/states'
import { ApiError } from '@/lib/api/client'
import { storeApi } from '@/lib/api/endpoints'
import { initRuntimeEnv, isInLiff } from '@/lib/liff/environment'

export default function StoreMenuPage() {
  const router = useRouter()
  const params = useParams<{ storeId: string }>()
  const storeId = params.storeId

  const [envReady, setEnvReady] = useState(false)
  useEffect(() => {
    let cancelled = false
    void initRuntimeEnv().then(() => {
      if (!cancelled) setEnvReady(true)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const enabled = envReady && isInLiff() && Boolean(storeId)

  const storeQuery = useQuery({
    queryKey: ['stores', storeId],
    queryFn: () => storeApi.get(storeId),
    enabled,
    retry: false, // 404 不需重試
  })

  const menuQuery = useQuery({
    queryKey: ['stores', storeId, 'menu-items'],
    queryFn: () => storeApi.menuItems(storeId),
    enabled,
    retry: false,
  })

  /** 返回清單。用 back() 而非 push()，以保留清單的排序與捲動位置。 */
  const goBack = () => {
    if (window.history.length > 1) router.back()
    else router.replace('/restaurants')
  }

  if (!envReady) return <LoadingState label="載入中…" />

  if (!isInLiff()) {
    return (
      <main className="px-4 py-6">
        <LiffOnlyNotice onBack={() => router.replace('/dashboard')} />
      </main>
    )
  }

  // 店家已不存在（可能於瀏覽期間被後台實刪除）——必須可返回，
  // 不得停在無法離開的錯誤畫面（FR-027）。
  const notFound =
    (storeQuery.error instanceof ApiError && storeQuery.error.status === 404) ||
    (menuQuery.error instanceof ApiError && menuQuery.error.status === 404)

  if (notFound) {
    return (
      <main className="px-4 py-6">
        <StoreNotFound onBack={goBack} />
      </main>
    )
  }

  if (storeQuery.isPending || menuQuery.isPending) {
    return <LoadingState label="載入餐點資訊…" />
  }

  const store = storeQuery.data
  const items = menuQuery.data?.menu_items ?? []

  return (
    <main className="space-y-4 px-4 py-4">
      <header className="space-y-1">
        <button
          type="button"
          onClick={goBack}
          className="text-xs font-bold text-slate-400 transition hover:text-slate-600"
        >
          ← 店家清單
        </button>
        <h1 className="text-base font-black">{store?.name}</h1>
        {/* 同名分店以地址區分——這裡顯示地址不是裝飾（FR-016）。 */}
        {store?.address && <p className="text-[11px] text-slate-400">{store.address}</p>}
      </header>

      {items.length === 0 ? (
        <NoMenuItems onBack={goBack} />
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            // key 用 id——同店家內允許同名餐點，不得去重（FR-016a）。
            <li key={item.id}>
              <MenuItemRow item={item} />
            </li>
          ))}
        </ul>
      )}

      <p className="pt-1 text-center text-[10px] leading-relaxed text-slate-400">
        以上營養數值由店家提供，為估算參考值，非醫療診斷或治療建議。
      </p>
    </main>
  )
}
