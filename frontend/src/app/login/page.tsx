'use client'

/**
 * 登入頁。★ 憲章原則 II 的分流點。
 *
 *   LIFF 環境 → 取 ID Token 自動登入，使用者無感（FR-003）
 *   web 環境  → 顯示「使用 LINE 登入」，導向 LINE 官方 OAuth（FR-004）
 *
 * 環境判斷失敗一律走 web 分支——絕不因此顯示空白或錯誤畫面。
 */

import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'

import { authApi } from '@/lib/api/endpoints'
import { redirectStore, tokenStore } from '@/lib/api/client'
import { env, isWebOAuthConfigured } from '@/lib/env'
import { getLiffIdToken } from '@/lib/liff/environment'
import { useRuntimeEnv } from '../providers'

const LINE_AUTHORIZE_URL = 'https://access.line.me/oauth2/v2.1/authorize'
const STATE_KEY = 'caluli.oauth_state'

function afterLogin(profileCompleted: boolean): string {
  if (!profileCompleted) return '/onboarding'
  return redirectStore.take() ?? '/dashboard'
}

export default function LoginPage() {
  const router = useRouter()
  const { env: runtime, loading } = useRuntimeEnv()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // --- LIFF 分支：自動登入 ---
  useEffect(() => {
    if (loading || runtime !== 'liff') return

    const idToken = getLiffIdToken()
    if (!idToken) {
      // LIFF 環境但拿不到 token：不卡死，讓使用者改用網頁流程。
      setError('無法取得 LINE 身分，請重新開啟或改用瀏覽器登入。')
      return
    }

    setBusy(true)
    authApi
      .loginWithLiff(idToken)
      .then((session) => {
        tokenStore.set(session.access_token)
        router.replace(afterLogin(session.profile_completed))
      })
      .catch(() => setError('登入失敗，請稍後再試一次。'))
      .finally(() => setBusy(false))
  }, [loading, runtime, router])

  // --- web 分支：使用者主動觸發 OAuth ---
  const startWebLogin = useCallback(() => {
    if (!isWebOAuthConfigured()) {
      setError('登入服務尚未設定完成，請聯繫服務人員。')
      return
    }

    const state = crypto.randomUUID()
    window.sessionStorage.setItem(STATE_KEY, state)

    const params = new URLSearchParams({
      response_type: 'code',
      client_id: env.lineChannelId!,
      redirect_uri: env.lineRedirectUri!,
      state,
      scope: 'openid profile',
    })
    window.location.href = `${LINE_AUTHORIZE_URL}?${params.toString()}`
  }, [])

  if (loading) {
    return <CenteredMessage title="載入中" detail="正在確認執行環境…" />
  }

  if (runtime === 'liff' && !error) {
    return <CenteredMessage title="登入中" detail="正在以 LINE 身分登入…" />
  }

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6">
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-tr from-brand-600 to-emerald-400 text-3xl text-white shadow-lg">
          🍱
        </div>
        <h1 className="text-2xl font-black">caluli</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          拍一張照片，掌握熱量與營養素
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="max-w-xs rounded-2xl bg-rose-50 px-4 py-3 text-center text-xs font-semibold text-rose-700 dark:bg-rose-950/40 dark:text-rose-300"
        >
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={startWebLogin}
        disabled={busy}
        className="w-full max-w-xs rounded-2xl bg-[#06C755] py-4 text-sm font-black text-white shadow-lg transition active:scale-95 disabled:opacity-60"
      >
        使用 LINE 登入
      </button>

      <p className="max-w-xs text-center text-[11px] leading-relaxed text-slate-400">
        本服務僅提供熱量與營養素估算參考，不提供醫療診斷或治療建議。
      </p>
    </main>
  )
}

function CenteredMessage({ title, detail }: { title: string; detail: string }) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-3 px-6">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-500" />
      <h1 className="text-sm font-bold">{title}</h1>
      <p className="text-xs text-slate-500">{detail}</p>
    </main>
  )
}
