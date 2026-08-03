'use client'

/**
 * 一般網頁 OAuth 回呼（FR-004）。
 *
 * 使用者拒絕授權或中途取消時，須顯示未登入狀態與可再次嘗試的操作，
 * **不得**出現錯誤畫面或空白頁（US1 情境 6）。
 */

import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'

import { redirectStore, tokenStore } from '@/lib/api/client'
import { authApi } from '@/lib/api/endpoints'
import { env } from '@/lib/env'

const STATE_KEY = 'caluli.oauth_state'

function CallbackInner() {
  const router = useRouter()
  const params = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const code = params.get('code')
    const state = params.get('state')
    const oauthError = params.get('error')

    // 使用者按了「取消」——這是正常操作，不是系統錯誤。
    if (oauthError) {
      setError('您已取消登入。若要使用服務，請再試一次。')
      return
    }

    if (!code || !state) {
      setError('登入資訊不完整，請重新登入。')
      return
    }

    const expected = window.sessionStorage.getItem(STATE_KEY)
    window.sessionStorage.removeItem(STATE_KEY)
    if (!expected || expected !== state) {
      setError('登入驗證失敗，請重新登入。')
      return
    }

    authApi
      .loginWithCode(code, env.lineRedirectUri!, state)
      .then((session) => {
        tokenStore.set(session.access_token)
        router.replace(
          session.profile_completed ? (redirectStore.take() ?? '/dashboard') : '/onboarding'
        )
      })
      .catch(() => setError('登入失敗，請稍後再試一次。'))
  }, [params, router])

  if (error) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-5 px-6">
        <p role="alert" className="max-w-xs text-center text-sm font-semibold text-slate-600 dark:text-slate-300">
          {error}
        </p>
        <button
          type="button"
          onClick={() => router.replace('/login')}
          className="rounded-2xl bg-brand-600 px-6 py-3 text-sm font-bold text-white shadow-lg transition active:scale-95"
        >
          回到登入頁
        </button>
      </main>
    )
  }

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-3">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-500" />
      <p className="text-xs text-slate-500">正在完成登入…</p>
    </main>
  )
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<main className="min-h-dvh" />}>
      <CallbackInner />
    </Suspense>
  )
}
