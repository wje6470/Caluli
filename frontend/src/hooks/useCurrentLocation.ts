'use client'

/**
 * 目前位置的取得與快取（research.md R-10）。
 *
 * ★ 為什麼用 TanStack Query 承載座標，而不是元件 state 或 sessionStorage
 * =====================================================================
 * spec 有兩條看似衝突的要求：
 *
 *   FR-026 / US2-4：從餐點頁返回時，清單維持原排序且**不得**重新請求定位權限
 *   US1-7        ：重新載入或再次進入該頁時，**必須**以當下座標重新計算
 *
 * 以 query cache 承載，兩者自然同時成立：
 *   - 頁面內導覽（client-side navigation）→ cache 仍在 → 命中，不觸發
 *     getCurrentPosition，不彈權限提示
 *   - 整頁重載 → cache 隨頁面銷毀 → 重新取得當下座標
 *
 * 其他做法都會壞掉其中一條：
 *   - sessionStorage：重載後沿用舊座標 → 違反 US1-7
 *   - 元件 state：返回時元件已卸載 → 重新請求權限 → 違反 FR-026
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { requestCurrentLocation, type LocationResult } from '@/lib/geo/location'

export const LOCATION_QUERY_KEY = ['geolocation'] as const

export function useCurrentLocation() {
  const queryClient = useQueryClient()

  const query = useQuery<LocationResult>({
    queryKey: LOCATION_QUERY_KEY,
    queryFn: requestCurrentLocation,
    // 取得後在本次頁面生命週期內不再重取（FR-026）。
    staleTime: Infinity,
    // ⚠️ retry: false 是必要的，不是保守設定。
    // requestCurrentLocation 永不 reject，所以自動重試其實不會觸發；
    // 但明確關閉可避免日後有人改成 throw 時，畫面卡在載入狀態並重複
    // 彈出權限提示——而 FR-009 要求的是**使用者主動**觸發的重試。
    retry: false,
    refetchOnWindowFocus: false,
  })

  /** 使用者主動重試定位（FR-009、FR-011）。成功後畫面自動切換為排序清單。 */
  const retry = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: LOCATION_QUERY_KEY })
  }, [queryClient])

  return {
    location: query.data ?? null,
    isPending: query.isPending,
    retry,
  }
}
