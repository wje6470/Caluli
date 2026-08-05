'use client'

/**
 * 拍照記帳流程：選擇來源 → Loading → 確認／引導／錯誤 → 儲存。
 *
 * 承載 US2 的前端全部需求。畫面切換完全由 useRecognition 的 phase 驅動，
 * 包含本輪不會觸發的 processing 分支（非同步遷移預留）。
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { EmptyResultGuide, ErrorState, LoadingState } from '@/components/capture/states'
import { RecognitionItemCard } from '@/components/capture/RecognitionItemCard'
import { useRecognition } from '@/hooks/useRecognition'
import { mealRecordApi } from '@/lib/api/endpoints'
import type { MealType } from '@/lib/api/types'
import {
  nutrientsOf,
  toDraftItems,
  toMealItemInput,
  type DraftItem,
} from '@/lib/capture/draft'
import { compressImage, validateFile, VALIDATION_MESSAGES } from '@/lib/capture/image'
import { formatGrams, formatKcal, sumNutrients } from '@/lib/nutrition'

const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: 'breakfast', label: '早餐' },
  { value: 'lunch', label: '午餐' },
  { value: 'dinner', label: '晚餐' },
  { value: 'snack', label: '點心' },
]

function defaultMealType(): MealType {
  const hour = new Date().getHours()
  if (hour >= 4 && hour < 11) return 'breakfast'
  if (hour >= 11 && hour < 16) return 'lunch'
  if (hour >= 16 && hour < 22) return 'dinner'
  return 'snack'
}

export default function CapturePage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const recognition = useRecognition()

  const cameraRef = useRef<HTMLInputElement>(null)
  const galleryRef = useRef<HTMLInputElement>(null)

  const [items, setItems] = useState<DraftItem[]>([])
  const [mealType, setMealType] = useState<MealType>(defaultMealType)
  const [fileError, setFileError] = useState<string | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)

  // object URL 隨 photoPreview 汰換或元件卸載即釋放，避免記憶體洩漏。
  useEffect(() => {
    return () => {
      if (photoPreview) URL.revokeObjectURL(photoPreview)
    }
  }, [photoPreview])

  const totals = useMemo(() => sumNutrients(items.map(nutrientsOf)), [items])

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return

      // 送出前驗證，不合法就不打 API（FR-019）。
      const invalid = validateFile(file)
      if (invalid) {
        setFileError(VALIDATION_MESSAGES[invalid])
        return
      }
      setFileError(null)

      const compressed = await compressImage(file)
      setPhotoPreview(URL.createObjectURL(compressed))
      await recognition.analyze(compressed)
    },
    [recognition]
  )

  // 辨識完成後把結果轉為可編輯草稿。
  const phase = recognition.phase
  const recognitionId = recognition.recognition?.id ?? null
  const draftKey = `${recognitionId}-${recognition.recognition?.retry_count ?? 0}`
  const [seededKey, setSeededKey] = useState<string | null>(null)
  if (phase === 'completed' && recognition.recognition && seededKey !== draftKey) {
    setSeededKey(draftKey)
    setItems(toDraftItems(recognition.recognition.items))
  }

  const save = useMutation({
    mutationFn: () =>
      mealRecordApi.create({
        recognition_id: recognitionId,
        meal_type: mealType,
        items: items.map(toMealItemInput),
      }),
    onSuccess: () => {
      // 儀表板即時反映此筆，使用者不需手動重新整理（FR-041）。
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['meal-records'] })
      queryClient.invalidateQueries({ queryKey: ['trends'] })
      router.replace('/dashboard')
    },
  })

  /** 放棄：不建立任何紀錄（FR-030）。 */
  const abandon = useCallback(() => {
    recognition.reset()
    setItems([])
    setSeededKey(null)
    setPhotoPreview(null)
    router.replace('/dashboard')
  }, [recognition, router])

  const retake = useCallback(() => {
    recognition.reset()
    setItems([])
    setSeededKey(null)
    setFileError(null)
    setPhotoPreview(null)
  }, [recognition])

  return (
    <main className="px-4 py-4">
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      <input
        ref={galleryRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      {phase === 'idle' && (
        <SourcePicker
          error={fileError}
          onCamera={() => cameraRef.current?.click()}
          onGallery={() => galleryRef.current?.click()}
          onBack={() => router.replace('/dashboard')}
        />
      )}

      {phase === 'processing' && <LoadingState />}

      {phase === 'empty' && (
        <EmptyResultGuide
          message={recognition.recognition?.message ?? null}
          onRetake={retake}
          onBack={abandon}
        />
      )}

      {phase === 'failed' && (
        <ErrorState
          error={recognition.error}
          failureCount={recognition.failureCount}
          canRetry={Boolean(recognitionId)}
          onRetry={() => {
            void recognition.retry()
          }}
          onRetake={retake}
          onBack={abandon}
        />
      )}

      {phase === 'completed' && (
        <section className="space-y-4">
          <header className="flex items-center justify-between">
            <button
              type="button"
              onClick={retake}
              className="text-xs font-bold text-slate-400 hover:text-slate-600"
            >
              ← 重拍
            </button>
            <span className="rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-black text-brand-600 dark:border-brand-800 dark:bg-brand-950/80 dark:text-brand-400">
              確認與微調
            </span>
            <span className="w-10" />
          </header>

          {photoPreview && (
            <img
              src={photoPreview}
              alt="剛拍攝的餐點照片"
              className="h-48 w-full rounded-3xl object-cover shadow-sm"
            />
          )}

          <div>
            <label htmlFor="meal-type" className="mb-1 block text-[11px] font-bold uppercase text-slate-400">
              餐點分類
            </label>
            <div id="meal-type" className="grid grid-cols-4 gap-2">
              {MEAL_TYPES.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setMealType(option.value)}
                  className={`rounded-xl py-2 text-xs font-bold transition ${
                    mealType === option.value
                      ? 'bg-brand-500 text-white shadow'
                      : 'bg-slate-100 text-slate-500 dark:bg-slate-800'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <ul className="space-y-3">
            {items.map((item, index) => (
              <li key={item.key}>
                <RecognitionItemCard
                  item={item}
                  onChange={(next) =>
                    setItems((prev) => prev.map((it, i) => (i === index ? next : it)))
                  }
                  // FR-036：移除後不列入合計、不被儲存。
                  onRemove={() => setItems((prev) => prev.filter((_, i) => i !== index))}
                />
              </li>
            ))}
          </ul>

          {items.length === 0 && (
            <p className="rounded-2xl bg-slate-100 px-4 py-6 text-center text-xs text-slate-500 dark:bg-slate-800">
              所有品項都被移除了。請重新拍攝，或返回不儲存。
            </p>
          )}

          {/* FR-033：合計隨任一品項變動即時更新 */}
          <div className="rounded-3xl bg-gradient-to-br from-slate-900 to-slate-800 p-4 text-white">
            <p className="text-[11px] font-bold uppercase tracking-wider text-brand-400">本次合計</p>
            <p className="numeric-stable mt-1 text-3xl font-black">
              {formatKcal(totals.calories_kcal)}
              <span className="ml-1 text-sm font-medium text-slate-400">kcal</span>
            </p>
            <p className="numeric-stable mt-2 text-[11px] text-slate-300">
              蛋白質 {formatGrams(totals.protein_g)}g ・ 碳水 {formatGrams(totals.carbs_g)}g ・ 脂肪{' '}
              {formatGrams(totals.fat_g)}g
            </p>
          </div>

          <p className="text-center text-[10px] leading-relaxed text-slate-400">
            以上為估算參考值，非醫療診斷或治療建議。
          </p>

          {save.isError && (
            <p role="alert" className="text-center text-xs font-semibold text-rose-600">
              儲存失敗，請再試一次。
            </p>
          )}

          <div className="space-y-2">
            <button
              type="button"
              disabled={items.length === 0 || save.isPending}
              onClick={() => save.mutate()}
              className="w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-4 text-sm font-black text-white shadow-xl transition active:scale-95 disabled:opacity-50"
            >
              {save.isPending ? '儲存中…' : '確認無誤，儲存至今日紀錄'}
            </button>
            <button
              type="button"
              onClick={abandon}
              className="w-full rounded-2xl py-3 text-xs font-bold text-slate-500 transition hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              放棄，不儲存
            </button>
          </div>
        </section>
      )}
    </main>
  )
}

function SourcePicker({
  error,
  onCamera,
  onGallery,
  onBack,
}: {
  error: string | null
  onCamera: () => void
  onGallery: () => void
  onBack: () => void
}) {
  return (
    <section className="flex min-h-[60dvh] flex-col items-center justify-center gap-6 px-2 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-tr from-brand-600 to-emerald-400 text-4xl shadow-xl">
        📷
      </div>
      <div>
        <h1 className="text-base font-black">拍照記帳</h1>
        <p className="mt-1 text-xs text-slate-400">拍一張餐點照片，AI 幫你估算熱量與營養素</p>
      </div>

      {error && (
        <p role="alert" className="max-w-xs rounded-2xl bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </p>
      )}

      <div className="flex w-full max-w-xs flex-col gap-2">
        <button
          type="button"
          onClick={onCamera}
          className="w-full rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-400 py-4 text-sm font-black text-white shadow-lg transition active:scale-95"
        >
          使用相機拍照
        </button>
        {/* 相機權限被拒時的替代路徑（FR-018）。 */}
        <button
          type="button"
          onClick={onGallery}
          className="w-full rounded-2xl border border-slate-200 py-4 text-sm font-bold transition active:scale-95 dark:border-slate-700"
        >
          從相簿選取
        </button>
        <button
          type="button"
          onClick={onBack}
          className="w-full py-2 text-xs font-bold text-slate-400 hover:text-slate-600"
        >
          返回
        </button>
      </div>

      <p className="max-w-xs text-[10px] leading-relaxed text-slate-400">
        若無法開啟相機，可能是瀏覽器權限被拒。請至瀏覽器設定開啟相機權限，或改用「從相簿選取」。
      </p>
    </section>
  )
}
