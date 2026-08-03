import type { Config } from 'tailwindcss'

/**
 * 視覺語彙抽取自 reference/prototype/caiuli.html（T111）。
 *
 * 抽成 theme token 而非散落在 class 字串中——視覺一致性靠設定檔保證，
 * 而不是靠人工比對每個元件。prototype 的**結構**不照抄，只取語彙。
 *
 * 深色模式採 class 策略（research.md R-05）：設定頁需要手動切換開關，
 * media 策略做不到。
 */
const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // prototype 的品牌綠（emerald 系）
        brand: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          700: '#047857',
          800: '#065f46',
          900: '#064e3b',
          950: '#022c22',
        },
        // 三大營養素的固定對應色，全站一致
        macro: {
          protein: '#6366f1', // indigo-500
          carbs: '#f59e0b', // amber-500
          fat: '#f43f5e', // rose-500
        },
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        // prototype 的卡片陰影階層
        card: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
        raised: '0 4px 12px -2px rgb(0 0 0 / 0.08)',
        hero: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
        'brand-glow': '0 10px 30px -10px rgb(16 185 129 / 0.4)',
      },
      fontWeight: {
        black: '900',
      },
      keyframes: {
        'sheet-up': {
          from: { transform: 'translateY(100%)' },
          to: { transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        // Modal 開合節奏（T114）
        'sheet-up': 'sheet-up 260ms cubic-bezier(0.32, 0.72, 0, 1)',
        'fade-in': 'fade-in 180ms ease-out',
        'scale-in': 'scale-in 200ms cubic-bezier(0.32, 0.72, 0, 1)',
        shimmer: 'shimmer 1.6s infinite',
      },
    },
  },
  plugins: [],
}

export default config
