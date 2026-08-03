'use client'

/**
 * 已登入區的外框與守衛。
 *
 * 兩道檢查（FR-013、FR-008）：
 *   1. 未登入            → /login，並記住原目標路徑
 *   2. 已登入但未建檔    → /onboarding，且直接輸入網址也擋得住
 */

import { useQuery } from '@tanstack/react-query'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect } from 'react'

import { redirectStore, tokenStore } from '@/lib/api/client'
import { profileApi } from '@/lib/api/endpoints'
import { BottomNav } from '@/components/ui/BottomNav'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()

  const hasToken = typeof window !== 'undefined' && Boolean(tokenStore.get())

  const { data, isPending, isError } = useQuery({
    queryKey: ['me'],
    queryFn: profileApi.me,
    enabled: hasToken,
  })

  useEffect(() => {
    if (typeof window === 'undefined') return

    if (!hasToken || isError) {
      redirectStore.set(pathname)
      router.replace('/login')
      return
    }

    // 尚未完成個人資訊填寫者不得進入主要頁面（FR-013）。
    if (data && !data.profile_completed) {
      router.replace('/onboarding')
    }
  }, [hasToken, isError, data, pathname, router])

  if (!hasToken || isPending || !data || !data.profile_completed) {
    return (
      <main className="flex min-h-dvh items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-500" />
      </main>
    )
  }

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col">
      <div className="flex-1 pb-20">{children}</div>
      <BottomNav />
    </div>
  )
}
