/**
 * ★ 憲章明列必測情境：非 LIFF 環境可完成登入流程（tasks.md T066）
 *
 * 核心斷言：`liff.init()` 失敗時必須降級為 'web' 且**不拋錯**——
 * 一般瀏覽器開啟時 init 本來就會失敗，那是正常路徑。若這裡拋錯，
 * 網頁版會直接白畫面。
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'

const liffMock = {
  init: vi.fn(),
  isInClient: vi.fn(),
  getIDToken: vi.fn(),
  isLoggedIn: vi.fn(),
  login: vi.fn(),
  closeWindow: vi.fn(),
}

vi.mock('@line/liff', () => ({ default: liffMock }))

const envMock = { liffId: 'test-liff-id' as string | null, apiBaseUrl: 'http://api.test' }
vi.mock('@/lib/env', () => ({ env: envMock }))

async function freshModule() {
  vi.resetModules()
  return import('@/lib/liff/environment')
}

beforeEach(() => {
  vi.clearAllMocks()
  envMock.liffId = 'test-liff-id'
})

describe('initRuntimeEnv', () => {
  it('在 LINE App 內回傳 liff', async () => {
    liffMock.init.mockResolvedValue(undefined)
    liffMock.isInClient.mockReturnValue(true)

    const { initRuntimeEnv } = await freshModule()
    await expect(initRuntimeEnv()).resolves.toBe('liff')
  })

  it('init 成功但不在 LINE App 內時回傳 web', async () => {
    liffMock.init.mockResolvedValue(undefined)
    liffMock.isInClient.mockReturnValue(false)

    const { initRuntimeEnv } = await freshModule()
    await expect(initRuntimeEnv()).resolves.toBe('web')
  })

  it('★ init 失敗時降級為 web 且不拋錯', async () => {
    liffMock.init.mockRejectedValue(new Error('liff.init failed outside LINE'))

    const { initRuntimeEnv } = await freshModule()
    // 不得 reject——這是一般瀏覽器的正常路徑。
    await expect(initRuntimeEnv()).resolves.toBe('web')
  })

  it('★ 未設定 LIFF ID 時降級為 web 且完全不呼叫 liff.init', async () => {
    envMock.liffId = null

    const { initRuntimeEnv } = await freshModule()
    await expect(initRuntimeEnv()).resolves.toBe('web')
    expect(liffMock.init).not.toHaveBeenCalled()
  })

  it('只判斷一次，之後回傳快取結果', async () => {
    liffMock.init.mockResolvedValue(undefined)
    liffMock.isInClient.mockReturnValue(true)

    const { initRuntimeEnv } = await freshModule()
    await Promise.all([initRuntimeEnv(), initRuntimeEnv(), initRuntimeEnv()])

    expect(liffMock.init).toHaveBeenCalledTimes(1)
  })
})

describe('LIFF 能力包裝在 web 環境的降級行為', () => {
  async function webModule() {
    liffMock.init.mockRejectedValue(new Error('not in LINE'))
    const mod = await freshModule()
    await mod.initRuntimeEnv()
    return mod
  }

  it('getLiffIdToken 回 null 而非拋錯', async () => {
    const { getLiffIdToken } = await webModule()
    expect(getLiffIdToken()).toBeNull()
    // 關鍵：連呼叫都不該發生，避免觸發 LIFF SDK 的內部錯誤。
    expect(liffMock.getIDToken).not.toHaveBeenCalled()
  })

  it('isLiffLoggedIn 回 false 而非拋錯', async () => {
    const { isLiffLoggedIn } = await webModule()
    expect(isLiffLoggedIn()).toBe(false)
    expect(liffMock.isLoggedIn).not.toHaveBeenCalled()
  })

  it('liffLogin 為 no-op 而非拋錯', async () => {
    const { liffLogin } = await webModule()
    expect(() => liffLogin()).not.toThrow()
    expect(liffMock.login).not.toHaveBeenCalled()
  })

  it('closeLiffWindow 回 false，呼叫端可據此改用一般導覽', async () => {
    const { closeLiffWindow } = await webModule()
    expect(closeLiffWindow()).toBe(false)
    expect(liffMock.closeWindow).not.toHaveBeenCalled()
  })
})

describe('LIFF 能力包裝在 LIFF 環境', () => {
  async function liffModule() {
    liffMock.init.mockResolvedValue(undefined)
    liffMock.isInClient.mockReturnValue(true)
    const mod = await freshModule()
    await mod.initRuntimeEnv()
    return mod
  }

  it('getLiffIdToken 回傳 SDK 提供的 token', async () => {
    liffMock.getIDToken.mockReturnValue('an-id-token')
    const { getLiffIdToken } = await liffModule()
    expect(getLiffIdToken()).toBe('an-id-token')
  })

  it('SDK 內部拋錯時仍回 null 而非讓錯誤外溢', async () => {
    liffMock.getIDToken.mockImplementation(() => {
      throw new Error('sdk exploded')
    })
    const { getLiffIdToken } = await liffModule()
    expect(getLiffIdToken()).toBeNull()
  })

  it('closeLiffWindow 成功時回 true', async () => {
    liffMock.closeWindow.mockReturnValue(undefined)
    const { closeLiffWindow } = await liffModule()
    expect(closeLiffWindow()).toBe(true)
  })
})
