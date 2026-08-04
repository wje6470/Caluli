/**
 * ★ FR-025：營養值的 null 與 0 必須雙向區分（tasks.md T034）
 *
 * 這支測試存在的唯一理由是抓 falsy 誤判：
 *
 *     value or '無資料'          ← 0 會變成「無資料」
 *     value ? fmt(value) : '無資料'
 *     {value && <span>…</span>}
 *
 * 這些寫法不會拋任何錯誤，型別檢查也過得了，只有在資料剛好是 0 時才會
 * 顯示錯誤資訊——而「無糖清茶 0 kcal」正是會發生的真實資料。
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MenuItemRow } from '@/components/restaurants/MenuItemRow'
import type { MenuItem } from '@/lib/api/types'

function makeItem(overrides: Partial<MenuItem> = {}): MenuItem {
  return {
    id: 'item-1',
    store_id: 'store-1',
    name: '測試餐點',
    calories_kcal: 780,
    protein_g: 28.5,
    carbs_g: 95,
    fat_g: 30.2,
    ...overrides,
  }
}

describe('MenuItemRow — 缺值（null）', () => {
  it('四個營養欄位皆為 null 時全部顯示「無資料」', () => {
    render(
      <MenuItemRow
        item={makeItem({ calories_kcal: null, protein_g: null, carbs_g: null, fat_g: null })}
      />
    )

    expect(screen.getAllByText('無資料')).toHaveLength(4)
  })

  it('缺值不得顯示為 0', () => {
    render(<MenuItemRow item={makeItem({ calories_kcal: null })} />)

    expect(screen.queryByText(/^0 kcal$/)).toBeNull()
    expect(screen.getByText('無資料')).toBeInTheDocument()
  })

  it('部分缺值時，其餘欄位仍正常顯示', () => {
    render(<MenuItemRow item={makeItem({ protein_g: null })} />)

    expect(screen.getByText('780 kcal')).toBeInTheDocument()
    expect(screen.getAllByText('無資料')).toHaveLength(1)
  })
})

describe('MenuItemRow — 零值（0）★ falsy 陷阱', () => {
  it('熱量為 0 時顯示「0 kcal」，不得顯示「無資料」', () => {
    render(<MenuItemRow item={makeItem({ calories_kcal: 0 })} />)

    expect(screen.getByText('0 kcal')).toBeInTheDocument()
    expect(screen.queryByText('無資料')).toBeNull()
  })

  it('四個欄位皆為 0 時全部顯示 0，完全不出現「無資料」', () => {
    render(
      <MenuItemRow
        item={makeItem({ name: '無糖清茶', calories_kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 })}
      />
    )

    expect(screen.getByText('0 kcal')).toBeInTheDocument()
    expect(screen.getAllByText('0 g')).toHaveLength(3)
    expect(screen.queryByText('無資料')).toBeNull()
  })

  it('0 與 null 在同一個畫面上可被區分', () => {
    render(
      <MenuItemRow item={makeItem({ calories_kcal: 0, protein_g: null, carbs_g: 0, fat_g: null })} />
    )

    expect(screen.getByText('0 kcal')).toBeInTheDocument()
    expect(screen.getAllByText('0 g')).toHaveLength(1) // carbs
    expect(screen.getAllByText('無資料')).toHaveLength(2) // protein, fat
  })
})

describe('MenuItemRow — 型別漂移的防禦（回歸測試）', () => {
  /**
   * ★ 這是實際發生過的當機：後端把 Decimal 序列化成 JSON 字串
   * （`"650.00"`），前端型別卻是 `number`，於是 `value.toFixed(1)`
   * 直接拋 `TypeError: value.toFixed is not a function`，整頁崩潰。
   *
   * 根因已在後端修正（schemas/store.py 改用 float，並有整合測試斷言
   * wire format）。這裡保留的是顯示層的防禦——一個純顯示元件不該因為
   * 上游型別漂移就讓整個畫面掛掉。
   */
  it('收到字串型別的數值時不崩潰，且仍正確顯示', () => {
    const withStrings = {
      ...makeItem(),
      // 刻意繞過型別檢查，模擬後端違反契約的情況。
      calories_kcal: '650.00' as unknown as number,
      protein_g: '25.00' as unknown as number,
      carbs_g: '80.50' as unknown as number,
      fat_g: '24.00' as unknown as number,
    }

    expect(() => render(<MenuItemRow item={withStrings} />)).not.toThrow()
    expect(screen.getByText('650 kcal')).toBeInTheDocument()
    expect(screen.getByText('80.5 g')).toBeInTheDocument()
  })

  it('字串 "0" 仍顯示為 0，不會變成「無資料」', () => {
    const zeroAsString = {
      ...makeItem(),
      calories_kcal: '0.00' as unknown as number,
    }

    render(<MenuItemRow item={zeroAsString} />)

    expect(screen.getByText('0 kcal')).toBeInTheDocument()
    expect(screen.queryByText('無資料')).toBeNull()
  })

  it('無法解析的值退回「無資料」而非顯示 NaN', () => {
    const garbage = {
      ...makeItem(),
      calories_kcal: 'abc' as unknown as number,
    }

    render(<MenuItemRow item={garbage} />)

    expect(screen.getByText('無資料')).toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).toBeNull()
  })
})

describe('MenuItemRow — 一般呈現', () => {
  it('顯示餐點名稱與四項營養值', () => {
    render(<MenuItemRow item={makeItem()} />)

    expect(screen.getByText('測試餐點')).toBeInTheDocument()
    expect(screen.getByText('780 kcal')).toBeInTheDocument()
    expect(screen.getByText('28.5 g')).toBeInTheDocument()
    expect(screen.getByText('95 g')).toBeInTheDocument()
    expect(screen.getByText('30.2 g')).toBeInTheDocument()
  })
})
