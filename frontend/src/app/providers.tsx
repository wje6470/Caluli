'use client'

/**
 * 全應用 Provider。
 *
 * 環境判斷（憲章原則 II）在此執行**一次**並快取於 Context，
 * 元件不再各自判斷。
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { createContext, useContext, useEffect, useState } from 'react'

import { setUnauthorizedHandler } from '@/lib/api/client'
import { initRuntimeEnv, type RuntimeEnv } from '@/lib/liff/environment'

type RuntimeEnvState = {
  env: RuntimeEnv | null
  /** 判斷尚未完成時為 true——此時不應渲染依賴環境的 UI。 */
  loading: boolean
}

const RuntimeEnvContext = createContext<RuntimeEnvState>({ env: null, loading: true })

export function useRuntimeEnv(): RuntimeEnvState {
  return useContext(RuntimeEnvContext)
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // 客戶端不保留離線業務資料（憲章原則 III）——快取僅為同一次
        // 瀏覽期間的即時性，不做持久化。
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: (failureCount, error) => {
          const retryable = (error as { retryable?: boolean })?.retryable
          return retryable === true && failureCount < 2
        },
        refetchOnWindowFocus: false,
      },
    },
  })
}

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [queryClient] = useState(makeQueryClient)
  const [state, setState] = useState<RuntimeEnvState>({ env: null, loading: true })

  useEffect(() => {
    let cancelled = false
    // 一定 resolve，不會 reject——init 失敗即降級為 web。
    initRuntimeEnv().then((env) => {
      if (!cancelled) setState({ env, loading: false })
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => router.replace('/login'))
  }, [router])

  return (
    <QueryClientProvider client={queryClient}>
      <RuntimeEnvContext.Provider value={state}>{children}</RuntimeEnvContext.Provider>
    </QueryClientProvider>
  )
}
