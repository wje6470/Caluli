/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 客戶端不保留離線業務資料（憲章原則 III）——不註冊 service worker、不做離線快取。
}

export default nextConfig
