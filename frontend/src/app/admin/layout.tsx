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

  // ★ 後台一律以淺色呈現（FR-046：不實作深色模式）。
  //
  // Tailwind 的 darkMode 是 'class'，主題由 <html class="dark"> 驅動。後台
  // 各處（含共用的 Modal）用的是 text-slate-700 這類深色文字，若 dark class
  // 生效，作業系統為深色模式的管理員會看到**深色底 + 深色字**——那不是
  // 「沒做深色模式」，是讀不到字。
  //
  // 在後台掛載期間移除該 class、離開時還原，等於明確退出主題切換，而不是
  // 為後台實作一套深色版本。只需這一處，共用元件也一併涵蓋。
  useEffect(() => {
    const root = document.documentElement
    const wasDark = root.classList.contains('dark')
    if (wasDark) root.classList.remove('dark')
    return () => {
      if (wasDark) root.classList.add('dark')
    }
  }, [])

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
      <main className="flex min-h-dvh items-center justify-center bg-slate-50">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-slate-500" />
      </main>
    )
  }

  // ★ 明確指定淺色底與文字色，不繼承 body 的配色。
  //
  // globals.css 的 body 帶 `dark:bg-slate-950 dark:text-slate-100`，而後台
  // 各處用的是 text-slate-900 這類深色文字（FR-046：後台不實作深色模式）。
  // 若沿用繼承來的底色，作業系統為深色模式的管理員會看到**深色底＋深色字**
  // ——那不是「沒做深色模式」，是讀不到字。
  //
  // 這裡的作法是明確退出主題切換而非實作深色版本，符合 FR-046 的意圖。
  return (
    <div className="min-h-dvh bg-slate-50 text-slate-800">
      <div className="mx-auto w-full max-w-6xl px-6 py-8">
        <header className="mb-6 flex items-baseline justify-between border-b border-slate-200 pb-4">
          <h1 className="text-xl font-bold text-slate-900">Caluli 後台管理</h1>
          <span className="text-sm text-slate-500">{data.display_name ?? '管理員'}</span>
        </header>
        {children}
      </div>
    </div>
  )
}
