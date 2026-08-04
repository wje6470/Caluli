/**
 * ★ FR-001〜FR-003、SC-006：推薦餐廳僅於 LIFF 入口提供（tasks.md T046、T049）
 *
 * 註：tasks.md 原本把這項規劃為 Playwright E2E。改以單元測試實作——第一輪
 * 並未建立 playwright config 或任何 e2e 測試（只有 package.json 的 script），
 * 為了這一條斷言引入完整 e2e 基礎設施（config ＋ 約 500MB 瀏覽器下載 ＋
 * LIFF 環境模擬）成本遠高於收益，而**要驗的東西完全相同**：非 LIFF 環境的
 * 導覽列不得出現「找餐廳」。這裡沿用第一輪 environment.test.ts 既有的
 * liff mock 手法，且能在 CI 中無條件執行。
 *
 * 路由守衛（直接輸入網址進入 /restaurants）的對應驗證見 quickstart V9 的
 * 手動情境。
 */

import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// vi.mock 會被提升到檔案頂端，因此 mock 物件必須以 vi.hoisted 建立，
// 否則工廠函式執行時 const 尚未初始化。
const environmentMock = vi.hoisted(() => ({
  initRuntimeEnv: vi.fn(),
  isInLiff: vi.fn(),
}))

vi.mock('@/lib/liff/environment', () => environmentMock)
vi.mock('next/navigation', () => ({ usePathname: () => '/dashboard' }))

import { BottomNav } from '@/components/ui/BottomNav'

beforeEach(() => {
  vi.clearAllMocks()
  environmentMock.initRuntimeEnv.mockResolvedValue('web')
})

describe('BottomNav — 入口限定', () => {
  it('LIFF 環境顯示「找餐廳」分頁', async () => {
    environmentMock.initRuntimeEnv.mockResolvedValue('liff')
    environmentMock.isInLiff.mockReturnValue(true)

    render(<BottomNav />)

    await waitFor(() => expect(screen.getByText('找餐廳')).toBeInTheDocument())
    expect(screen.getByText('找餐廳').closest('a')).toHaveAttribute('href', '/restaurants')
  })

  it('一般網頁環境不顯示「找餐廳」分頁（FR-002）', async () => {
    environmentMock.isInLiff.mockReturnValue(false)

    render(<BottomNav />)

    await waitFor(() => expect(environmentMock.initRuntimeEnv).toHaveBeenCalled())
    expect(screen.queryByText('找餐廳')).toBeNull()
  })

  it('第一輪的四個分頁在兩種環境都存在，不受本輪影響', async () => {
    environmentMock.isInLiff.mockReturnValue(false)

    render(<BottomNav />)

    await waitFor(() => expect(environmentMock.initRuntimeEnv).toHaveBeenCalled())
    for (const label of ['首頁', '拍照記帳', '趨勢', '我的']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('★ 環境判定完成前不得閃現「找餐廳」（research.md R-03）', () => {
    // initRuntimeEnv 尚未 resolve——模擬判定進行中的那一瞬間。
    environmentMock.initRuntimeEnv.mockReturnValue(new Promise(() => {}))
    environmentMock.isInLiff.mockReturnValue(true)

    render(<BottomNav />)

    // 首次渲染（同步）就必須看不到。若元件樂觀顯示，一般網頁會先閃現
    // 分頁再消失——這是 FR-002 明確禁止的。
    expect(screen.queryByText('找餐廳')).toBeNull()
  })
})
