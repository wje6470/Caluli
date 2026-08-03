import { redirect } from 'next/navigation'

/**
 * 根路由。
 *
 * 本應用的實際頁面都在 /login、/onboarding、/(app)/* 之下，原本沒有 `/`，
 * 導致直接開啟網域會 404——而 LIFF 的 Endpoint URL 通常正是填根網域。
 *
 * 這裡以真實路由（而非 vercel.json 的 redirects）處理，理由是後者只在
 * Vercel 生效且依賴部署設定被正確讀取；寫成頁面則本機 dev、任何 host
 * 都一致。
 *
 * 導向 /dashboard 而非 /login：(app)/layout.tsx 的守衛會依登入與建檔狀態
 * 自動分流（未登入 → /login，未建檔 → /onboarding），一條路徑涵蓋三種情況。
 */
export default function RootPage() {
  redirect('/dashboard')
}
