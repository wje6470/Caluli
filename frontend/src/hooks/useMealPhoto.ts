'use client'

/** 已存在紀錄的照片：需帶 Bearer token 取得，故轉為 blob object URL 供 <img> 使用。 */

import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { fetchAuthedBlob } from '@/lib/api/client'
import { mealRecordApi } from '@/lib/api/endpoints'

export function useMealPhoto(recordId: string, hasPhoto: boolean): string | null {
  const query = useQuery({
    queryKey: ['meal-photo', recordId],
    queryFn: ({ signal }: { signal: AbortSignal }) =>
      fetchAuthedBlob(mealRecordApi.photoUrl(recordId), signal),
    enabled: hasPhoto,
    // 照片存檔後不會變更，取得一次即可長期沿用。
    staleTime: Infinity,
    gcTime: Infinity,
  })

  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!query.data) return
    const objectUrl = URL.createObjectURL(query.data)
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [query.data])

  return url
}
