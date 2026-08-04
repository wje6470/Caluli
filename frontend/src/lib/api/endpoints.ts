/** 型別化的端點呼叫。對應 contracts/openapi.yaml。 */

import { api } from './client'
import type {
  AdminSession,
  Store,
  StoreInput,
  StoreWithCount,
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

/**
 * 管理端（第三輪）。路徑以 /admin 起始，沿用同一個 NEXT_PUBLIC_API_BASE_URL
 * （已含 /api/v1）——刻意不另立 base URL，見 research.md R-01。
 */
export const adminApi = {
  /**
   * 確認目前使用者具備管理員身分。
   *
   * 用「呼叫受保護端點看它通不通過」來判斷權限，與後端實際的授權判斷走
   * 同一條路徑；若改讀 /me 的欄位自行判斷，就會出現第二套邏輯（R-11）。
   *
   * 非管理員會拿到 403，一般使用者未登入則是 401。
   */
  me: () => api.get<AdminSession>('/admin/me'),

  stores: {
    list: () => api.get<{ stores: StoreWithCount[] }>('/admin/stores'),
    create: (input: StoreInput) => api.post<Store>('/admin/stores', input),
    update: (id: string, input: Partial<StoreInput>) =>
      api.patch<Store>(`/admin/stores/${id}`, input),
    /** 連帶刪除該店家底下的所有餐點——呼叫前務必二次確認（FR-038）。 */
    remove: (id: string) => api.delete<void>(`/admin/stores/${id}`),
  },
}
