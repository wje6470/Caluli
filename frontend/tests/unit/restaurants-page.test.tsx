/**
 * ★ SC-004／SC-005：四種狀態畫面的**分流**（tasks.md T042、T043、T045）
 *
 * 前面的測試各自驗了「錯誤碼 → 狀態」（location.test.ts）與「狀態 → 畫面」
 * （states.tsx 的元件），但**沒有任何測試驗「哪個狀態該顯示哪個畫面」**
 * ——而規格最容易違反的地方正是這裡：把「拒絕授權」與「定位失敗」合併成
 * 同一個畫面（FR-007 明文禁止），或是把兩種空狀態混為一談（R-05）。
 *
 * 這支測試守的是頁面的分流邏輯本身。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { LocationResult } from '@/lib/geo/location'
import type { Store, StoreListResponse } from '@/lib/api/types'

const mocks = vi.hoisted(() => ({
  useCurrentLocation: vi.fn(),
  list: vi.fn(),
  initRuntimeEnv: vi.fn(),
  isInLiff: vi.fn(),
  replace: vi.fn(),
}))

vi.mock('@/hooks/useCurrentLocation', () => ({
  useCurrentLocation: mocks.useCurrentLocation,
}))
vi.mock('@/lib/api/endpoints', () => ({ storeApi: { list: mocks.list } }))
vi.mock('@/lib/liff/environment', () => ({
  initRuntimeEnv: mocks.initRuntimeEnv,
  isInLiff: mocks.isInLiff,
}))
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: mocks.replace }) }))

import RestaurantsPage from '@/app/(app)/restaurants/page'

function makeStore(overrides: Partial<Store> = {}): Store {
  return {
    id: 'store-1',
    name: '測試店家',
    address: '臺北市中正區測試路 1 號',
    latitude: 25.0478,
    longitude: 121.517,
    distance_m: 120,
    ...overrides,
  }
}

function makeResponse(overrides: Partial<StoreListResponse> = {}): StoreListResponse {
  return {
    mode: 'nearby',
    radius_km: 5,
    total_store_count: 1,
    stores: [makeStore()],
    ...overrides,
  }
}

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

function setLocation(location: LocationResult | null) {
  mocks.useCurrentLocation.mockReturnValue({
    location,
    isPending: false,
    retry: vi.fn(),
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.initRuntimeEnv.mockResolvedValue('liff')
  mocks.isInLiff.mockReturnValue(true)
  mocks.list.mockResolvedValue(makeResponse())
})

describe('定位成功', () => {
  it('顯示店家清單與距離', async () => {
    setLocation({ status: 'granted', coords: { lat: 25.0478, lng: 121.517 } })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('測試店家')).toBeInTheDocument())
    expect(screen.getByText('120 公尺')).toBeInTheDocument()
    // 地址是分辨同名分店的依據，必須顯示（FR-016）。
    expect(screen.getByText('臺北市中正區測試路 1 號')).toBeInTheDocument()
  })

  it('帶座標查詢（附近模式）', async () => {
    setLocation({ status: 'granted', coords: { lat: 25.0478, lng: 121.517 } })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() =>
      expect(mocks.list).toHaveBeenCalledWith({ lat: 25.0478, lng: 121.517 })
    )
  })
})

describe('★ 拒絕授權 vs 定位失敗必須是不同畫面（FR-007、SC-005）', () => {
  it('拒絕授權：指向權限設定，且**沒有**重試按鈕', async () => {
    setLocation({ status: 'denied' })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('已拒絕定位權限')).toBeInTheDocument())
    // 重試對「被拒絕」沒有意義——還是會被擋。給了只會誤導使用者。
    expect(screen.queryByRole('button', { name: '重試定位' })).toBeNull()
    // 仍呈現全部店家清單，不阻斷模組（FR-008）。
    await waitFor(() => expect(screen.getByText('測試店家')).toBeInTheDocument())
  })

  it('定位失敗：指向裝置設定，且**有**重試按鈕', async () => {
    setLocation({ status: 'unavailable', reason: 'position_unavailable' })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('無法取得目前位置')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: '重試定位' })).toBeInTheDocument()
    // 同樣呈現全部店家清單（FR-009）。
    await waitFor(() => expect(screen.getByText('測試店家')).toBeInTheDocument())
  })

  it('逾時的文案與「裝置定位關閉」不同（下一步不一樣）', async () => {
    setLocation({ status: 'unavailable', reason: 'timeout' })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('定位花費的時間過長')).toBeInTheDocument())
    expect(screen.queryByText('無法取得目前位置')).toBeNull()
  })

  it('拒絕與失敗兩種畫面不會同時出現', async () => {
    setLocation({ status: 'denied' })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('已拒絕定位權限')).toBeInTheDocument())
    expect(screen.queryByText('無法取得目前位置')).toBeNull()
    expect(screen.queryByText('定位花費的時間過長')).toBeNull()
  })

  it('定位被拒時以不帶座標查詢（全部模式）', async () => {
    setLocation({ status: 'denied' })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith(undefined))
  })
})

describe('★ 兩種空狀態必須可區分（FR-019、R-05）', () => {
  it('附近查無店家（total > 0）：提供「改看全部店家」', async () => {
    setLocation({ status: 'granted', coords: { lat: 22.6, lng: 120.3 } })
    mocks.list.mockResolvedValue(makeResponse({ stores: [], total_store_count: 15 }))

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('附近查無店家')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: '改看全部店家' })).toBeInTheDocument()
    expect(screen.queryByText('目前尚無店家資料')).toBeNull()
  })

  it('資料庫無店家（total = 0）：**不**提供改看操作', async () => {
    setLocation({ status: 'granted', coords: { lat: 25.0478, lng: 121.517 } })
    mocks.list.mockResolvedValue(makeResponse({ stores: [], total_store_count: 0 }))

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('目前尚無店家資料')).toBeInTheDocument())
    // 提供了只會導向另一個空清單。
    expect(screen.queryByRole('button', { name: '改看全部店家' })).toBeNull()
    expect(screen.queryByText('附近查無店家')).toBeNull()
  })
})

describe('入口限定（FR-003）', () => {
  it('非 LIFF 環境顯示降級說明，不白畫面', async () => {
    mocks.initRuntimeEnv.mockResolvedValue('web')
    mocks.isInLiff.mockReturnValue(false)
    setLocation(null)

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText('此功能僅於 LINE 內提供')).toBeInTheDocument())
    // 非 LIFF 不得發出查詢。
    expect(mocks.list).not.toHaveBeenCalled()
  })
})

describe('免責聲明（FR-037、憲章原則 VII）', () => {
  it('清單頁標示營養數值為估算參考值', async () => {
    setLocation({ status: 'granted', coords: { lat: 25.0478, lng: 121.517 } })

    render(<RestaurantsPage />, { wrapper })

    await waitFor(() => expect(screen.getByText(/估算參考值/)).toBeInTheDocument())
  })
})
