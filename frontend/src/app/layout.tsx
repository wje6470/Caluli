import type { Metadata, Viewport } from 'next'

import { Providers } from './providers'
import '@/styles/globals.css'

export const metadata: Metadata = {
  title: 'caluli — 智慧營養記錄',
  description: '拍一張照片就掌握熱量與營養素。數值為估算參考，非醫療診斷。',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#10b981',
}

/**
 * 在 hydration 前套用主題，避免深色模式閃爍（tasks.md T112）。
 * 必須是同步 inline script，放在 body 最前面。
 */
const themeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem('caluli.theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (stored === 'dark' || (!stored && prefersDark)) {
      document.documentElement.classList.add('dark');
    }
  } catch (e) {}
})();
`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
