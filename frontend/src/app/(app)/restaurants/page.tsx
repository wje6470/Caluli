'use client'

/**
 * 推薦餐廳 — 店家清單（US1、US3）。
 *
 * 畫面完全由「定位狀態 × 查詢結果」驅動，四種狀態彼此可區分（SC-004）：
 *
 *   定位成功 → 5 公里內最近 10 家，依距離排序，顯示距離
 *   拒絕授權 → 全部店家（不排序、無距離）＋ 指向權限設定的說明（FR-008）
 *   定位失敗 → 全部店家 ＋ 指向裝置設定的說明 ＋ 「重試定位」（FR-009）
 *   附近查無 → 依 total_store_count 分為「附近查無」與「尚無資料」（R-05）
 *
 * ⚠️ 僅於 LIFF 入口提供（FR-001〜FR-003）。非 LIFF 環境顯示降級說明，
 *    不得白畫面或錯誤畫面（憲章原則 II）。
 */

import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import {
  LiffOnlyNotice,
  LoadingState,
  LocationDeniedNotice,
  LocationUnavailableNotice,
  NoNearbyStores,
  NoStoresAtAll,
} from '@/components/restaurants/states'
import { StoreCard } from '@/components/restaurants/StoreCard'
import { useCurrentLocation } from '@/hooks/useCurrentLocation'
import { storeApi } from '@/lib/api/endpoints'
import { initRuntimeEnv, isInLiff } from '@/lib/liff/environment'

export default function RestaurantsPage() {
  const router = useRouter()
  const { location, isPending: locationPending, retry } = useCurrentLocation()

  // 使用者按下「改看全部店家」後，即使有座標也改用全部模式（FR-019）。
  const [forceAllStores, setForceAllStores] = useState(false)

  // 環境判定完成前不做任何結論——判定中一律顯示載入狀態，避免非 LIFF
  // 環境短暫閃現本功能（FR-002、research.md R-03）。
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

  const coords =
    !forceAllStores && location?.status === 'granted' ? location.coords : undefined

  const {
    data,
    isPending: listPending,
    isError,
  } = useQuery({
    queryKey: ['stores', coords?.lat ?? null, coords?.lng ?? null],
    queryFn: () => storeApi.list(coords),
    // 定位狀態未定前不查詢——否則會先以全部模式打一次，取得座標後再打一次。
    enabled: envReady && isInLiff() && !locationPending,
  })

  if (!envReady) return <LoadingState label="載入中…" />

  if (!isInLiff()) {
    return (
      <main className="px-4 py-6">
        <LiffOnlyNotice onBack={() => router.replace('/dashboard')} />
      </main>
    )
  }

  return (
    <main className="space-y-4 px-4 py-4">
      <header>
        <h1 className="text-base font-black">推薦餐廳</h1>
        <p className="mt-0.5 text-xs text-slate-400">
          {coords ? '依您目前位置，由近至遠' : '全部店家'}
        </p>
      </header>

      {/* 定位的降級說明置於清單上方——說明與替代清單同時呈現，
          使用者不必在「看說明」與「看店家」之間二選一（FR-008、FR-009）。 */}
      {!forceAllStores && location?.status === 'denied' && <LocationDeniedNotice />}
      {!forceAllStores && location?.status === 'unavailable' && (
        <LocationUnavailableNotice reason={location.reason} onRetry={retry} />
      )}

      {(locationPending || listPending) && <LoadingState label="正在尋找附近的店家…" />}

      {isError && (
        <p role="alert" className="rounded-2xl bg-rose-50 px-4 py-3 text-center text-xs font-semibold text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
          店家清單載入失敗，請稍後再試。
        </p>
      )}

      {data && data.stores.length > 0 && (
        <ul className="space-y-2">
          {data.stores.map((store) => (
            // key 用 id 而非 name——同名分店會造成 key 重複與渲染錯亂（FR-016a）。
            <li key={store.id}>
              <StoreCard store={store} />
            </li>
          ))}
        </ul>
      )}

      {/* 兩種空狀態的差別只看得出來，是因為回應帶了 total_store_count。
          只看 stores.length === 0 無從分辨（research.md R-05）。 */}
      {data && data.stores.length === 0 && data.total_store_count > 0 && (
        <NoNearbyStores
          radiusKm={data.radius_km ?? 5}
          onShowAll={() => setForceAllStores(true)}
        />
      )}
      {data && data.stores.length === 0 && data.total_store_count === 0 && <NoStoresAtAll />}

      <p className="pt-1 text-center text-[10px] leading-relaxed text-slate-400">
        營養數值由店家提供，為估算參考值，非醫療診斷或治療建議。
      </p>
    </main>
  )
}
