/**
 * ★ 核心互動驗證（tasks.md T089）
 *
 * 兩個斷言：
 *   1. 調整份量後，熱量與營養素**立即**依 per_100g × g/100 更新
 *   2. 整個過程**沒有任何 fetch**——這是 SC-003 的驗收條件
 *
 * 第 2 點是最容易在重構時被破壞的：只要有人「順手」把換算改成呼叫後端，
 * 即時性就沒了，而畫面看起來仍然正常。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'

import { RecognitionItemCard } from '@/components/capture/RecognitionItemCard'
import type { DraftItem } from '@/lib/capture/draft'
import { clampPortion, scaleNutrients, sumNutrients } from '@/lib/nutrition'
import { ZERO_NUTRIENTS } from '@/lib/nutrition'

// 滷肉飯每 100g（與後端種子資料一致）
const PER_100G = { calories_kcal: 187, protein_g: 6.2, carbs_g: 26.1, fat_g: 6.5 }

const ITEM: DraftItem = {
  key: '0-滷肉飯',
  foodReferenceId: 'ref-1',
  name: '滷肉飯',
  confidence: 0.93,
  per100g: PER_100G,
  defaultGrams: 250,
  grams: 250,
  manualNutrients: ZERO_NUTRIENTS,
  candidates: [
    { food_reference_id: 'ref-1', name: '滷肉飯', confidence: 0.93, default_portion_grams: 250, per_100g: PER_100G },
    {
      food_reference_id: 'ref-2',
      name: '白飯',
      confidence: 0.04,
      default_portion_grams: 200,
      per_100g: { calories_kcal: 130, protein_g: 2.7, carbs_g: 28.2, fat_g: 0.3 },
    },
  ],
  userModified: false,
}

/** 食物搜尋用到 TanStack Query，需要 Provider；查詢在無關鍵字時不會啟用。 */
function withQuery(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>
}

function Harness({ initial = ITEM }: { initial?: DraftItem }) {
  const [item, setItem] = useState(initial)
  return withQuery(<RecognitionItemCard item={item} onChange={setItem} onRemove={() => {}} />)
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('純函式換算', () => {
  it('依 per_100g × 克數/100 計算', () => {
    const result = scaleNutrients(PER_100G, 250)
    expect(result.calories_kcal).toBeCloseTo(467.5, 5)
    expect(result.protein_g).toBeCloseTo(15.5, 5)
    expect(result.carbs_g).toBeCloseTo(65.25, 5)
    expect(result.fat_g).toBeCloseTo(16.25, 5)
  })

  it('調整為 375g 時（quickstart V3 的驗證數值）', () => {
    expect(scaleNutrients(PER_100G, 375).calories_kcal).toBeCloseTo(701.25, 5)
  })

  it('份量受上下限約束（FR-034）', () => {
    expect(clampPortion(0)).toBe(1)
    expect(clampPortion(-50)).toBe(1)
    expect(clampPortion(99999)).toBe(5000)
    expect(clampPortion(Number.NaN)).toBe(1)
  })

  it('合計為各品項相加（FR-033）', () => {
    const total = sumNutrients([scaleNutrients(PER_100G, 100), scaleNutrients(PER_100G, 200)])
    expect(total.calories_kcal).toBeCloseTo(561, 5)
  })
})

describe('RecognitionItemCard 即時互動', () => {
  it('預設份量來自系統設定值並顯示對應熱量', () => {
    render(<Harness />)
    expect(screen.getByLabelText('滷肉飯份量（公克）')).toHaveValue(250)
    expect(screen.getByText('468')).toBeInTheDocument() // 467.5 → 四捨五入
  })

  it('★ 調整份量後熱量即時更新，且全程沒有任何 fetch', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const user = userEvent.setup()

    render(<Harness />)
    const input = screen.getByLabelText('滷肉飯份量（公克）')

    await user.clear(input)
    await user.type(input, '375')

    // 701.25 → 701
    expect(await screen.findByText('701')).toBeInTheDocument()

    // ★ 這是 SC-003 的核心：換算是純前端運算。
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('標示預設份量為估計值而非拍照量測', () => {
    render(<Harness />)
    expect(screen.getByText(/系統預設 250g（估計值，非拍照量測）/)).toBeInTheDocument()
  })

  it('改選候選食物後以新食物的 per_100g 與預設份量重算（FR-035）', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByRole('button', { name: '辨識錯了？換一個' }))
    await user.click(screen.getByRole('button', { name: /白飯/ }))

    // 白飯預設 200g：130 × 2 = 260 kcal
    expect(await screen.findByText('260')).toBeInTheDocument()
    expect(screen.getByLabelText('白飯份量（公克）')).toHaveValue(200)
  })

  it('查無營養資料時標示無法自動換算並提供手動輸入（FR-037）', () => {
    render(<Harness initial={{ ...ITEM, per100g: null, defaultGrams: null }} />)
    expect(screen.getByText(/不在營養資料庫中，無法自動換算/)).toBeInTheDocument()
    expect(screen.getByLabelText('食物名稱')).toBeInTheDocument()
    expect(screen.queryByLabelText(/份量滑桿/)).not.toBeInTheDocument()
  })

  it('提供移除品項的操作（FR-036）', async () => {
    const onRemove = vi.fn()
    const user = userEvent.setup()
    render(withQuery(<RecognitionItemCard item={ITEM} onChange={() => {}} onRemove={onRemove} />))

    await user.click(screen.getByRole('button', { name: '移除 滷肉飯' }))
    expect(onRemove).toHaveBeenCalledOnce()
  })
})
