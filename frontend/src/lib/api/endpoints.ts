/** 型別化的端點呼叫。對應 contracts/openapi.yaml。 */

import { api } from './client'
import type {
  DashboardResponse,
  HealthProfile,
  HealthProfileInput,
  MealRecord,
  MealRecordInput,
  MenuItemListResponse,
  MeResponse,
  MetricKey,
  Recognition,
  SessionResponse,
  FoodReference,
  Store,
  StoreListResponse,
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
 * 推薦餐廳（第二輪）。全部為唯讀查詢——新增／修改／刪除屬第三輪管理員後台，
 * 本輪不提供也不預留（FR-029）。
 */
export const storeApi = {
  /**
   * 店家清單。
   *
   * 帶座標 → 附近模式（5 公里內、依距離排序、最多 10 家）。
   * 不帶座標 → 全部模式（依名稱排序、無距離），供定位被拒／失敗，
   * 以及「附近查無店家」時的「改看全部店家」使用。
   *
   * ⚠️ 座標必須成對傳送。只傳其一後端會回 422（而非無聲退回全部模式），
   * 避免前端誤以為使用者位置已納入計算。
   */
  list: (coords?: { lat: number; lng: number }) =>
    api.get<StoreListResponse>(
      coords ? `/stores?lat=${coords.lat}&lng=${coords.lng}` : '/stores'
    ),

  get: (storeId: string) => api.get<Store>(`/stores/${storeId}`),

  menuItems: (storeId: string) =>
    api.get<MenuItemListResponse>(`/stores/${storeId}/menu-items`),
}
