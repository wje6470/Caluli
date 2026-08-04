'use client'

/**
 * 推薦餐廳的各種非正常狀態畫面。
 *
 * ★ SC-004／SC-005：這些畫面**必須彼此可區分**
 * ==============================================
 * 規格明文要求「拒絕授權」與「定位服務失敗」分開處理（FR-007），最容易犯的
 * 錯就是把兩者合併成一個「定位失敗」畫面。差異在於：
 *
 *   拒絕授權   → 問題在**瀏覽器權限設定**，重試沒有意義（還是會被擋）
 *                → 指向權限設定，**不提供**重試按鈕
 *   定位失敗   → 問題在**裝置定位服務或訊號**，重試是合理的下一步
 *                → 指向裝置設定，**提供**「重試定位」
 *
 * 同理，兩種空狀態也必須可區分：
 *
 *   附近查無店家（total > 0）→ 提供「改看全部店家」
 *   尚無店家資料（total = 0）→ **不提供**，那只會導向另一個空清單
 */

import { PermissionNotice } from '@/components/ui/PermissionNotice'
import type { LocationUnavailableReason } from '@/lib/geo/location'

/** FR-008：使用者拒絕定位授權。指向權限設定，無重試。 */
export function LocationDeniedNotice() {
  return (
    <PermissionNotice
      icon="📍"
      title="已拒絕定位權限"
      description="沒有您的位置就無法計算距離，以下改為顯示全部店家（不依距離排序）。"
      hint="想看附近的店家？請至瀏覽器或 LINE 的網站設定中開啟此站的「位置」權限，然後重新整理頁面。"
    />
  )
}

/**
 * FR-009／FR-010：定位服務失敗。指向裝置設定，**提供重試**。
 *
 * 文案依 reason 再細分——逾時與「裝置定位關閉」的下一步不同，
 * 混為一談會讓使用者照著錯誤的指示白忙。
 */
export function LocationUnavailableNotice({
  reason,
  onRetry,
}: {
  reason: LocationUnavailableReason
  onRetry: () => void
}) {
  const copy: Record<LocationUnavailableReason, { title: string; description: string; hint: string }> = {
    timeout: {
      title: '定位花費的時間過長',
      description: '目前取不到您的位置，以下改為顯示全部店家（不依距離排序）。',
      hint: '移動到窗邊或戶外通常會更快取得訊號，再試一次看看。',
    },
    position_unavailable: {
      title: '無法取得目前位置',
      description: '裝置的定位服務可能已關閉，或目前收不到定位訊號。以下改為顯示全部店家。',
      hint: '請確認裝置的「定位服務」已開啟（iOS：設定 → 隱私權與安全性 → 定位服務；Android：設定 → 位置）。',
    },
    unsupported: {
      title: '此裝置不支援定位',
      description: '目前的瀏覽器或裝置沒有提供定位功能，以下改為顯示全部店家。',
      hint: '您仍可瀏覽所有店家與餐點資訊。',
    },
    invalid_coords: {
      title: '取得的位置不正確',
      description: '收到的座標超出有效範圍，無法用來計算距離。以下改為顯示全部店家。',
      hint: '這通常是暫時性的訊號問題，稍後再試一次即可。',
    },
  }

  const { title, description, hint } = copy[reason]

  return (
    <PermissionNotice
      icon="🛰️"
      tone="warning"
      title={title}
      description={description}
      hint={hint}
      // 拒絕授權的畫面**沒有**這顆按鈕——這是兩者最明顯的區別（SC-005）。
      primaryAction={{ label: '重試定位', onClick: onRetry }}
    />
  )
}

/** FR-019：資料庫有店家，但 5 公里內沒有。提供「改看全部店家」。 */
export function NoNearbyStores({
  radiusKm,
  onShowAll,
}: {
  radiusKm: number
  onShowAll: () => void
}) {
  return (
    <PermissionNotice
      icon="🔍"
      title="附近查無店家"
      description={`您目前位置 ${radiusKm} 公里內還沒有收錄的店家。`}
      hint="可以改看全部店家，或稍後在其他地點再試試。"
      primaryAction={{ label: '改看全部店家', onClick: onShowAll }}
    />
  )
}

/**
 * US3-5：資料庫完全沒有店家資料。
 *
 * ⚠️ **不提供**「改看全部店家」——那只會導向另一個空清單。這正是回應需要
 * total_store_count 的理由（research.md R-05）：只看 stores: [] 無從分辨
 * 這個狀態與上面那個。
 */
export function NoStoresAtAll() {
  return (
    <PermissionNotice
      icon="🏪"
      title="目前尚無店家資料"
      description="店家資訊還在建置中，敬請期待。"
    />
  )
}

/** FR-024：店家存在但尚未登錄餐點。空清單是正常結果，不是錯誤。 */
export function NoMenuItems({ onBack }: { onBack: () => void }) {
  return (
    <PermissionNotice
      icon="🍽️"
      title="此店家尚未提供餐點資訊"
      description="這家店還沒有登錄餐點的營養資料。"
      secondaryAction={{ label: '返回店家清單', onClick: onBack }}
    />
  )
}

/** FR-027：店家不存在（可能於瀏覽期間被後台刪除）。 */
export function StoreNotFound({ onBack }: { onBack: () => void }) {
  return (
    <PermissionNotice
      icon="❓"
      tone="warning"
      title="此店家已不存在"
      description="這家店可能已經下架或被移除。"
      primaryAction={{ label: '返回店家清單', onClick: onBack }}
    />
  )
}

/** FR-003：非 LIFF 環境。不得白畫面或錯誤畫面（憲章原則 II）。 */
export function LiffOnlyNotice({ onBack }: { onBack: () => void }) {
  return (
    <PermissionNotice
      icon="💬"
      title="此功能僅於 LINE 內提供"
      description="推薦餐廳需要在 LINE App 中開啟才能使用。"
      hint="其他功能（拍照記帳、儀表板、趨勢）在一般瀏覽器中皆可正常使用。"
      primaryAction={{ label: '返回首頁', onClick: onBack }}
    />
  )
}

/** 通用載入狀態。 */
export function LoadingState({ label }: { label: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[40dvh] flex-col items-center justify-center gap-3"
    >
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-500 dark:border-slate-800 dark:border-t-brand-400" />
      <p className="text-xs text-slate-400">{label}</p>
    </div>
  )
}
