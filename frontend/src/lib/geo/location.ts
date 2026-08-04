/**
 * 目前位置取得（推薦餐廳模組，第二輪）。
 *
 * ★ 為什麼這是全新實作，而不是沿用第一輪（research.md R-02）
 * ============================================================
 * brief 要求「比照第一輪相機權限的既有實作模式」。實際查核的結果是——
 * **該模式不存在於程式碼中**：
 *
 *   第一輪取得相機的方式是 <input type="file" capture="environment">，
 *   權限完全由作業系統的檔案選擇器處理，前端沒有呼叫任何 Permissions API。
 *   因此第一輪**偵測不到權限是否被拒**，它的「被拒處理」是一段恆常顯示的
 *   靜態提示文字加上「從相簿選取」按鈕，而非依權限狀態分支。
 *
 * 所以「比照第一輪」只能在 **UX 原則層級**成立，本模組沿用其三項原則：
 *   1. 不預先請求——使用者主動進入該功能時才請求
 *   2. 被拒不阻斷——一律提供替代路徑（第一輪為相簿，本輪為全部店家清單）
 *   3. 明示如何恢復——畫面上說明如何重新開啟權限
 *
 * ★ 而在取得機制上，定位與相機有本質差異——這正是本輪能滿足 FR-007 的原因
 * ==========================================================================
 * navigator.geolocation 的錯誤物件帶 code，可精確區分規格要求的兩類情境；
 * file input 完全沒有這個訊號。
 *
 *   code 1 PERMISSION_DENIED    → 'denied'      → 指向權限設定，無重試
 *   code 2 POSITION_UNAVAILABLE → 'unavailable' → 指向裝置定位設定，可重試
 *   code 3 TIMEOUT              → 'unavailable' → 同上（reason 區分為 timeout）
 *
 * **這個映射是整條降級路徑唯一的分歧點**，映射錯了所有畫面都會走錯，
 * 且不會拋任何錯誤。tests/unit/location.test.ts 專門守著它。
 */

/** 座標取得的等待上限（毫秒）。逾時視為定位失敗，不無限期停留在載入狀態（FR-010）。 */
export const LOCATION_TIMEOUT_MS = 10_000

export type Coords = { lat: number; lng: number }

export type LocationUnavailableReason = 'position_unavailable' | 'timeout' | 'unsupported' | 'invalid_coords'

export type LocationResult =
  | { status: 'granted'; coords: Coords }
  /** 使用者拒絕授權（FR-008）——退回全部店家清單，指向權限設定，不提供重試。 */
  | { status: 'denied' }
  /** 定位服務失敗（FR-009）——退回全部店家清單，指向裝置設定，**提供重試**。 */
  | { status: 'unavailable'; reason: LocationUnavailableReason }

/** 座標是否落在有效範圍內。 */
export function isValidCoords(lat: number, lng: number): boolean {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  )
}

/**
 * 請求目前位置。
 *
 * **永不 reject**——所有失敗情境都以 LocationResult 表達。理由：呼叫端需要
 * 依失敗種類分流到不同畫面，而 throw 會讓 TanStack Query 落入通用錯誤處理，
 * 使「拒絕」與「失敗」再度合流，正是 FR-007 禁止的行為。
 */
export function requestCurrentLocation(): Promise<LocationResult> {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      resolve({ status: 'unavailable', reason: 'unsupported' })
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude
        const lng = position.coords.longitude

        // 明顯不合理的座標視同定位失敗，不送給後端（research.md R-07）。
        // 送出去只會得到通用 API 錯誤，而非帶重試按鈕的定位失敗畫面。
        if (!isValidCoords(lat, lng)) {
          resolve({ status: 'unavailable', reason: 'invalid_coords' })
          return
        }

        resolve({ status: 'granted', coords: { lat, lng } })
      },
      (error) => {
        // 逐一對照 code，不用 if/else 省略——這裡的分支是規格要求的核心。
        if (error.code === error.PERMISSION_DENIED) {
          resolve({ status: 'denied' })
          return
        }
        if (error.code === error.TIMEOUT) {
          resolve({ status: 'unavailable', reason: 'timeout' })
          return
        }
        resolve({ status: 'unavailable', reason: 'position_unavailable' })
      },
      {
        timeout: LOCATION_TIMEOUT_MS,
        maximumAge: 0, // 不使用快取座標——每次進入頁面都要當下的位置（US1-7）
        enableHighAccuracy: false, // 店家排序不需要高精度，低精度更快也更省電
      }
    )
  })
}
