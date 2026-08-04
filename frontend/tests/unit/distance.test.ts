/** 距離格式化（tasks.md T024）。 */

import { describe, expect, it } from 'vitest'

import { formatDistance } from '@/lib/format/distance'

describe('formatDistance', () => {
  it.each([
    [0, '0 公尺'],
    [55, '60 公尺'], // 取整至十位——不呈現定位本身沒有的精度
    [120, '120 公尺'],
    [999, '1000 公尺'],
  ])('%s 公尺 → %s', (metres, expected) => {
    expect(formatDistance(metres)).toBe(expected)
  })

  it.each([
    [1000, '1.0 公里'],
    [1550, '1.6 公里'],
    [4770, '4.8 公里'],
  ])('%s 公尺 → %s', (metres, expected) => {
    expect(formatDistance(metres)).toBe(expected)
  })

  it('無效輸入回空字串，不顯示 NaN', () => {
    expect(formatDistance(NaN)).toBe('')
    expect(formatDistance(-1)).toBe('')
  })
})
