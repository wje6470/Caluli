import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

/**
 * 註：未使用 eslint-config-next——該套件（15.5.x）僅提供 .eslintrc 進入點，
 * 其 @rushstack/eslint-patch 與 ESLint 9 的 flat config 不相容。改以
 * typescript-eslint + react-hooks 組成等效規則集。
 */
export default [
  {
    ignores: [
      'node_modules/**',
      '.next/**',
      'out/**',
      'dist/**',
      'build/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      'next-env.d.ts',
      '**/*.min.js',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],

      // ★ 憲章原則 II：LIFF SDK 只能經由 lib/liff/environment.ts 存取。
      // 直接 import 會讓環境判斷散落，並使「非 LIFF 環境誤呼叫 LIFF 專屬
      // 功能」重新變得可能。
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@line/liff',
              message:
                'LIFF SDK 只能在 src/lib/liff/environment.ts 內使用。請改用 getRuntimeEnv() 與包裝後的能力函式。',
            },
          ],
        },
      ],
    },
  },
  {
    // 唯一允許直接使用 LIFF SDK 的檔案。
    files: ['src/lib/liff/environment.ts'],
    rules: { 'no-restricted-imports': 'off' },
  },
  {
    files: ['tests/**/*.{ts,tsx}'],
    languageOptions: { globals: { ...globals.node } },
  },
]
