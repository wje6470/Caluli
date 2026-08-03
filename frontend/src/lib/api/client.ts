/**
 * 型別化 API client。
 *
 * 憲章原則 III：所有客戶端呼叫同一組端點，不因執行環境分岔；
 * 不在本機保留任何業務資料，token 以外一律即時取自後端。
 */

import { env } from '@/lib/env'
import type { ApiErrorBody } from './types'

const TOKEN_KEY = 'caluli.access_token'
const REDIRECT_KEY = 'caluli.post_login_path'

export class ApiError extends Error {
  readonly code: string
  readonly retryable: boolean
  readonly status: number

  constructor(status: number, code: string, message: string, retryable: boolean) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryable = retryable
  }

  /** 網路層失敗（未收到回應）也視為可重試。 */
  static network(): ApiError {
    return new ApiError(0, 'NETWORK_ERROR', '網路連線不穩定，請確認連線後再試一次。', true)
  }
}

export const tokenStore = {
  get(): string | null {
    if (typeof window === 'undefined') return null
    return window.localStorage.getItem(TOKEN_KEY)
  },
  set(token: string): void {
    window.localStorage.setItem(TOKEN_KEY, token)
  },
  clear(): void {
    window.localStorage.removeItem(TOKEN_KEY)
  },
}

/** 記住 401 發生時的目標路徑，登入完成後回到原處（FR-008）。 */
export const redirectStore = {
  get(): string | null {
    if (typeof window === 'undefined') return null
    return window.sessionStorage.getItem(REDIRECT_KEY)
  },
  set(path: string): void {
    window.sessionStorage.setItem(REDIRECT_KEY, path)
  },
  take(): string | null {
    const value = redirectStore.get()
    if (value) window.sessionStorage.removeItem(REDIRECT_KEY)
    return value
  },
}

type RequestOptions = {
  method?: string
  body?: unknown
  formData?: FormData
  signal?: AbortSignal
  /** 401 時是否觸發導向登入。辨識輪詢等背景呼叫可關閉。 */
  redirectOnUnauthorized?: boolean
}

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

async function parseError(response: Response): Promise<ApiError> {
  let code = 'INTERNAL_ERROR'
  let message = '系統發生問題，請稍後再試。'
  let retryable = false
  try {
    const body = (await response.json()) as ApiErrorBody
    if (body?.error) {
      code = body.error.code
      message = body.error.message
      retryable = body.error.retryable
    }
  } catch {
    // 回應不是 JSON——保留預設訊息，不外露技術細節。
  }
  return new ApiError(response.status, code, message, retryable)
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, formData, signal, redirectOnUnauthorized = true } = options

  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw ApiError.network()
  }

  if (response.status === 401) {
    tokenStore.clear()
    if (redirectOnUnauthorized && typeof window !== 'undefined') {
      redirectStore.set(window.location.pathname + window.location.search)
      onUnauthorized?.()
    }
    throw await parseError(response)
  }

  if (!response.ok) throw await parseError(response)

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  postForm: <T>(path: string, formData: FormData, signal?: AbortSignal) =>
    request<T>(path, { method: 'POST', formData, signal }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
