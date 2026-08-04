'use client'

/**
 * 後台外框與管理員守衛（spec FR-017）。
 *
 * ★ 為什麼不放在 (app) 路由群組內
 * ================================
 * (app)/layout.tsx 有一道「已登入但未建檔 → 強制導向 /onboarding」的守衛。
 * 管理員是內部人員，多半從未填寫過身高體重等健康檔案——後台若放進 (app)，
 * 管理員一進來就會被踢去 onboarding，**永遠進不了後台**。
 *
 * 分開還有兩個附帶好處：
 *   1. BottomNav 完全不需修改，也就不可能不小心露出後台連結（FR-017）
 *   2. (app) 的 max-w-md 手機版寬度不適用於後台的桌機表格介面
 *
 * ★ 權限的實質保證在後端
 * ======================
 * 這裡的導離只是體驗處理，不是權限控制。每一支管理端 API 都在後端獨立
 * 驗證（憲章原則 IV）；即使有人繞過前端直接打 API，一樣會被擋下。
 */

import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

import { ApiError, tokenStore } from '@/lib/api/client'
import { adminApi } from '@/lib/api/endpoints'

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const hasToken = typeof window !== 'undefined' && Boolean(tokenStore.get())

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['admin', 'me'],
    queryFn: adminApi.me,
    enabled: hasToken,
    // 403 是明確的「你不是管理員」，重試沒有意義。
    retry: false,
  })

  useEffect(() => {
    if (typeof window === 'undefined') return

    if (!hasToken) {
      router.replace('/login')
      return
    }

    if (isError) {
      // 401 由 api client 自行導向登入；403 代表已登入但非管理員，
      // 導回一般使用者的主頁面，不顯示任何後台相關訊息。
      if (error instanceof ApiError && error.status === 403) {
        router.replace('/dashboard')
      }
    }
  }, [hasToken, isError, error, router])

  // ★ 確認為管理員之前不渲染任何後台內容（FR-017）。
  //   不得閃現表格骨架、欄位名稱或功能標題——那等同對一般使用者
  //   洩漏了後台的存在與結構。
  if (!hasToken || isPending || isError || !data) {
    return (
      <main className="flex min-h-dvh items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-slate-500" />
      </main>
    )
  }

  return (
    <div className="mx-auto min-h-dvh w-full max-w-6xl px-6 py-8">
      <header className="mb-6 flex items-baseline justify-between border-b border-slate-200 pb-4">
        <h1 className="text-xl font-bold text-slate-900">Caluli 後台管理</h1>
        <span className="text-sm text-slate-500">{data.display_name ?? '管理員'}</span>
      </header>
      {children}
    </div>
  )
}
