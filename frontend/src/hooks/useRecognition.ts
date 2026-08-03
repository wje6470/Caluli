'use client'

/**
 * 辨識流程狀態機。
 *
 * ★ research.md R-07：以 `status` 驅動畫面，並**預留 processing 分支**。
 *   本輪後端是同步呼叫，`processing` 不會被觸發；但畫面與狀態轉換先寫好，
 *   未來改為非同步（輪詢／推送）時只需改本 hook 取得結果的方式，
 *   畫面層完全不用動。
 */

import { useCallback, useRef, useState } from 'react'

import { ApiError } from '@/lib/api/client'
import { recognitionApi } from '@/lib/api/endpoints'
import type { Recognition } from '@/lib/api/types'

export type RecognitionPhase =
  | 'idle'
  /** 上傳中 / 等待辨識服務（本輪同步，畫面顯示 Loading）。 */
  | 'processing'
  /** 辨識完成且有品項。 */
  | 'completed'
  /** ★ 辨識完成但未偵測到食物——這是**成功**，不是錯誤（FR-027）。 */
  | 'empty'
  /** 逾時 / 服務不可用 / 回應異常。 */
  | 'failed'

export type RecognitionState = {
  phase: RecognitionPhase
  recognition: Recognition | null
  error: ApiError | null
  /** 連續失敗次數。達 3 次時另外顯示「返回」出口（FR-029）。 */
  failureCount: number
}

const INITIAL: RecognitionState = {
  phase: 'idle',
  recognition: null,
  error: null,
  failureCount: 0,
}

function classify(recognition: Recognition): RecognitionPhase {
  if (recognition.status === 'processing') return 'processing'
  if (recognition.status === 'failed') return 'failed'
  // items 為空 = 未偵測到食物。走 empty 而非 failed——前端據此顯示
  // 專屬引導畫面，而不是通用錯誤畫面或空清單。
  return recognition.items.length === 0 ? 'empty' : 'completed'
}

export function useRecognition() {
  const [state, setState] = useState<RecognitionState>(INITIAL)
  const abortRef = useRef<AbortController | null>(null)

  const settle = useCallback((recognition: Recognition) => {
    setState((prev) => ({
      phase: classify(recognition),
      recognition,
      error: null,
      // 成功即重置失敗計數。
      failureCount: recognition.status === 'failed' ? prev.failureCount + 1 : 0,
    }))
  }, [])

  const fail = useCallback((error: unknown) => {
    setState((prev) => ({
      phase: 'failed',
      recognition: prev.recognition,
      error: error instanceof ApiError ? error : null,
      failureCount: prev.failureCount + 1,
    }))
  }, [])

  /** 上傳照片並辨識。 */
  const analyze = useCallback(
    async (photo: File | Blob) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setState((prev) => ({ ...prev, phase: 'processing', error: null }))

      try {
        const result = await recognitionApi.create(photo, controller.signal)
        settle(result)
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        fail(error)
      }
    },
    [settle, fail]
  )

  /**
   * 重試。★ FR-028：**不需重新選取照片**——後端重用第一次已存檔的照片。
   * 沒有 recognition id 時（第一次上傳就失敗）無法重試，回 false 讓
   * 呼叫端引導使用者重新拍攝。
   */
  const retry = useCallback(async (): Promise<boolean> => {
    const id = state.recognition?.id
    if (!id) return false

    setState((prev) => ({ ...prev, phase: 'processing', error: null }))
    try {
      settle(await recognitionApi.retry(id))
    } catch (error) {
      fail(error)
    }
    return true
  }, [state.recognition?.id, settle, fail])

  /**
   * 非同步遷移預留：輪詢既有辨識資源。
   * 本輪不會用到（同步呼叫已直接拿到結果），但接口先備好——
   * 改為非同步時，analyze() 收到 processing 後改呼叫這裡即可。
   */
  const poll = useCallback(
    async (id: string) => {
      try {
        settle(await recognitionApi.get(id))
      } catch (error) {
        fail(error)
      }
    },
    [settle, fail]
  )

  /** 放棄流程（取消／離開）——不建立任何紀錄（FR-030）。 */
  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setState(INITIAL)
  }, [])

  return { ...state, analyze, retry, poll, reset }
}
