/** 型別化的端點呼叫。對應 contracts/openapi.yaml。 */

import { api } from './client'
import type {
  DashboardResponse,
  HealthProfile,
  HealthProfileInput,
  MealRecord,
  MealRecordInput,
  MeResponse,
  MetricKey,
  Recognition,
  SessionResponse,
  FoodReference,
  TrendResponse,
} from './types'

export const authApi = {
  /** LIFF 入口：以 ID Token 換 session。 */
  loginWithLiff: (idToken: string) =>
    api.post<SessionResponse>('/auth/line/liff', { id_token: idToken }),

  /** 一般網頁入口：以 authorization code 換 session。 */
  loginWithCode: (code: string, redirectUri: string, state: string) =>
    api.post<SessionResponse>('/auth/line/callback', {
      code,
      redirect_uri: redirectUri,
      state,
    }),
}

export const profileApi = {
  me: () => api.get<MeResponse>('/me'),
  upsert: (input: HealthProfileInput) => api.put<HealthProfile>('/me/profile', input),
}

export const recognitionApi = {
  create: (photo: File | Blob, signal?: AbortSignal) => {
    const form = new FormData()
    form.append('photo', photo, 'meal.jpg')
    return api.postForm<Recognition>('/recognitions', form, signal)
  },
  get: (id: string) => api.get<Recognition>(`/recognitions/${id}`),
  /** 重試不需重新上傳照片——後端重用既有檔案（FR-028）。 */
  retry: (id: string) => api.post<Recognition>(`/recognitions/${id}/retry`),
}

export const mealRecordApi = {
  list: (date?: string) => api.get<{ records: MealRecord[] }>(`/meal-records${date ? `?date=${date}` : ''}`),
  create: (input: MealRecordInput) => api.post<MealRecord>('/meal-records', input),
  update: (id: string, input: MealRecordInput) => api.patch<MealRecord>(`/meal-records/${id}`, input),
  remove: (id: string) => api.delete<void>(`/meal-records/${id}`),
  photoUrl: (id: string) => `/meal-records/${id}/photo`,
}

export const analyticsApi = {
  dashboard: (date?: string) =>
    api.get<DashboardResponse>(`/dashboard${date ? `?date=${date}` : ''}`),
  trends: (rangeDays: 7 | 14 | 30, metric: MetricKey) =>
    api.get<TrendResponse>(`/trends?range_days=${rangeDays}&metric=${metric}`),
}

export const foodApi = {
  search: (q: string) =>
    api.get<{ foods: FoodReference[] }>(`/foods/search?q=${encodeURIComponent(q)}`),
}
