/**
 * 執行環境判斷與 LIFF 能力包裝。
 *
 * ★ 憲章原則 II — 前端不再限定 LIFF
 * =====================================
 * 本模組是**全應用唯一**可以 import `@line/liff` 的地方（由 ESLint 的
 * no-restricted-imports 強制）。元件拿不到原始 liff 物件，只能透過這裡
 * 包裝過的函式，因此「非 LIFF 環境誤呼叫 LIFF 專屬功能」在型別層面就
 * 不容易發生。
 *
 * 關鍵設計：`liff.init()` 失敗 → **降級為 web，不拋錯**。
 * 一般瀏覽器開啟時 init 本來就會失敗，那是正常路徑而非異常路徑。
 * 把它當錯誤處理會讓網頁版直接白畫面。
 */

import liff from '@line/liff'
import { env } from '@/lib/env'

export type RuntimeEnv = 'liff' | 'web'

let initPromise: Promise<RuntimeEnv> | null = null
let resolvedEnv: RuntimeEnv | null = null

/**
 * 判斷目前執行環境。全應用只實際判斷一次，之後回傳快取結果。
 *
 * 任何失敗情況（未設定 LIFF ID、init 拋錯、非瀏覽器環境）一律回 'web'。
 */
export async function initRuntimeEnv(): Promise<RuntimeEnv> {
  if (resolvedEnv) return resolvedEnv
  if (initPromise) return initPromise

  initPromise = (async (): Promise<RuntimeEnv> => {
    // 伺服器端渲染時沒有 LIFF，一律視為 web。
    if (typeof window === 'undefined') return 'web'

    // 未設定 LIFF ID = 這個部署不走 LIFF，直接降級。
    if (!env.liffId) return 'web'

    try {
      await liff.init({ liffId: env.liffId })
      return liff.isInClient() ? 'liff' : 'web'
    } catch {
      // init 失敗是一般瀏覽器的正常結果，不是錯誤。
      return 'web'
    }
  })()

  resolvedEnv = await initPromise
  return resolvedEnv
}

/** 取得已判定的環境。尚未判定時回 null（呼叫端應等待 initRuntimeEnv）。 */
export function getRuntimeEnv(): RuntimeEnv | null {
  return resolvedEnv
}

export function isInLiff(): boolean {
  return resolvedEnv === 'liff'
}

// ---------------------------------------------------------------------------
// LIFF 能力包裝
//
// 每個函式在 web 環境都有明確的降級行為，絕不拋錯。
// ---------------------------------------------------------------------------

/**
 * 取得 LINE ID Token（僅 LIFF 環境）。
 * web 環境回 null——呼叫端應改走一般網頁 OAuth 流程。
 */
export function getLiffIdToken(): string | null {
  if (!isInLiff()) return null
  try {
    return liff.getIDToken()
  } catch {
    return null
  }
}

/** 是否已於 LIFF 內登入。web 環境永遠回 false。 */
export function isLiffLoggedIn(): boolean {
  if (!isInLiff()) return false
  try {
    return liff.isLoggedIn()
  } catch {
    return false
  }
}

/** 觸發 LIFF 登入。web 環境為 no-op（呼叫端改走 OAuth）。 */
export function liffLogin(): void {
  if (!isInLiff()) return
  try {
    liff.login()
  } catch {
    // 降級：不中斷流程。
  }
}

/**
 * 關閉 LIFF 視窗。
 * web 環境無此概念 → 回 false，呼叫端可據此改用一般導覽。
 */
export function closeLiffWindow(): boolean {
  if (!isInLiff()) return false
  try {
    liff.closeWindow()
    return true
  } catch {
    return false
  }
}

/** 僅供測試重設快取。 */
export function __resetRuntimeEnvForTests(): void {
  initPromise = null
  resolvedEnv = null
}
