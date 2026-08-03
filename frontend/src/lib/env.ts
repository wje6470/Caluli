/**
 * 前端環境變數存取。
 *
 * 憲章原則 II：缺少 NEXT_PUBLIC_LIFF_ID 時**不得崩潰**——那是一般瀏覽器
 * 部署的正常情況，應降級為 web 模式而非拋錯。因此 liffId 是 optional。
 */

const required = (name: string, value: string | undefined): string => {
  if (!value) {
    throw new Error(`缺少必要環境變數 ${name}`)
  }
  return value
}

export const env = {
  /** 後端 API base URL。缺少即無法運作，故為必要。 */
  apiBaseUrl: required('NEXT_PUBLIC_API_BASE_URL', process.env.NEXT_PUBLIC_API_BASE_URL),

  /** LIFF app ID。缺少時視為未設定 LIFF，一律走 web 模式。 */
  liffId: process.env.NEXT_PUBLIC_LIFF_ID ?? null,

  /** LINE Login channel ID，供一般網頁 OAuth 使用。 */
  lineChannelId: process.env.NEXT_PUBLIC_LINE_CHANNEL_ID ?? null,

  /** OAuth 回呼位址。 */
  lineRedirectUri: process.env.NEXT_PUBLIC_LINE_REDIRECT_URI ?? null,
} as const

/** 一般網頁 OAuth 是否可用（設定不全時，登入頁需顯示可理解的說明而非空白）。 */
export const isWebOAuthConfigured = (): boolean =>
  Boolean(env.lineChannelId && env.lineRedirectUri)
