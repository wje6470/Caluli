/**
 * ★ FR-007：拒絕授權與定位失敗必須分開處理（tasks.md T022、T040）
 *
 * 這個錯誤碼映射是整條降級路徑**唯一的分歧點**——映射錯了，使用者會看到
 * 錯誤的說明與錯誤的可用操作（例如拒絕權限卻給「重試定位」，重試當然還是
 * 被擋），而程式不會拋任何錯誤。
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { isValidCoords, requestCurrentLocation } from '@/lib/geo/location'

const getCurrentPosition = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('navigator', { geolocation: { getCurrentPosition } })
})

/** 模擬瀏覽器的 GeolocationPositionError（帶 code 常數）。 */
function positionError(code: number) {
  return { code, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 }
}

describe('requestCurrentLocation', () => {
  it('成功時回傳 granted 與座標', async () => {
    getCurrentPosition.mockImplementation((success) =>
      success({ coords: { latitude: 25.0478, longitude: 121.517 } })
    )

    const result = await requestCurrentLocation()

    expect(result).toEqual({ status: 'granted', coords: { lat: 25.0478, lng: 121.517 } })
  })

  it('PERMISSION_DENIED (code 1) → denied，而非 unavailable', async () => {
    getCurrentPosition.mockImplementation((_s, failure) => failure(positionError(1)))

    const result = await requestCurrentLocation()

    // 這是 FR-008 的入口——若誤判為 unavailable，畫面會給出無用的「重試定位」。
    expect(result.status).toBe('denied')
  })

  it('POSITION_UNAVAILABLE (code 2) → unavailable，而非 denied', async () => {
    getCurrentPosition.mockImplementation((_s, failure) => failure(positionError(2)))

    const result = await requestCurrentLocation()

    // 誤判為 denied 會讓使用者被導去改瀏覽器權限，但問題其實在裝置定位服務。
    expect(result).toEqual({ status: 'unavailable', reason: 'position_unavailable' })
  })

  it('TIMEOUT (code 3) → unavailable 且 reason 為 timeout', async () => {
    getCurrentPosition.mockImplementation((_s, failure) => failure(positionError(3)))

    const result = await requestCurrentLocation()

    expect(result).toEqual({ status: 'unavailable', reason: 'timeout' })
  })

  it('裝置不支援定位時回 unavailable，不拋錯', async () => {
    vi.stubGlobal('navigator', {})

    await expect(requestCurrentLocation()).resolves.toEqual({
      status: 'unavailable',
      reason: 'unsupported',
    })
  })

  it('座標超出有效範圍時視為定位失敗，不送給後端', async () => {
    getCurrentPosition.mockImplementation((success) =>
      success({ coords: { latitude: 999, longitude: 0 } })
    )

    const result = await requestCurrentLocation()

    // 送給後端只會得到通用 API 錯誤，而非帶重試按鈕的定位失敗畫面（R-07）。
    expect(result).toEqual({ status: 'unavailable', reason: 'invalid_coords' })
  })

  it('永不 reject——所有失敗都以 LocationResult 表達', async () => {
    getCurrentPosition.mockImplementation((_s, failure) => failure(positionError(2)))

    // 若改成 throw，TanStack Query 會落入通用錯誤處理，
    // 讓「拒絕」與「失敗」再度合流——正是 FR-007 禁止的。
    await expect(requestCurrentLocation()).resolves.toBeDefined()
  })

  it('設定 10 秒逾時上限（FR-010）', async () => {
    getCurrentPosition.mockImplementation((success) =>
      success({ coords: { latitude: 25, longitude: 121 } })
    )

    await requestCurrentLocation()

    expect(getCurrentPosition).toHaveBeenCalledWith(
      expect.any(Function),
      expect.any(Function),
      expect.objectContaining({ timeout: 10_000, maximumAge: 0 })
    )
  })
})

describe('isValidCoords', () => {
  it.each([
    [25.0478, 121.517, true],
    [0, 0, true],
    [-90, -180, true],
    [90, 180, true],
    [90.1, 0, false],
    [0, 180.1, false],
    [NaN, 0, false],
    [Infinity, 0, false],
  ])('(%s, %s) → %s', (lat, lng, expected) => {
    expect(isValidCoords(lat, lng)).toBe(expected)
  })
})
