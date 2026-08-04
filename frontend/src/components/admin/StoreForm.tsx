'use client'

/**
 * 店家新增／編輯表單。
 *
 * 介面以精簡為原則（FR-045）：原生 input + 既有 Modal，不引入元件庫、
 * 不做視覺打磨、不支援深色模式。重點在寫入正確性而非呈現。
 */

import { useState } from 'react'

import { Modal } from '@/components/ui/Modal'
import type { Store, StoreInput } from '@/lib/api/types'

type Props = {
  /** 有值＝編輯既有店家；null＝新增。 */
  store: Store | null
  onSubmit: (input: StoreInput) => void
  onCancel: () => void
  pending: boolean
  /** 後端回傳的錯誤訊息（已是可直接呈現的中文）。 */
  error: string | null
}

const label = 'block text-sm font-medium text-slate-700'
const input =
  'mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

export function StoreForm({ store, onSubmit, onCancel, pending, error }: Props) {
  const [name, setName] = useState(store?.name ?? '')
  const [address, setAddress] = useState(store?.address ?? '')
  // 座標以字串保存：空字串代表「未設定」，與 "0" 是不同的狀態。
  const [latitude, setLatitude] = useState(store?.latitude ?? '')
  const [longitude, setLongitude] = useState(store?.longitude ?? '')
  const [localError, setLocalError] = useState<string | null>(null)

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setLocalError(null)

    const hasLat = latitude.trim() !== ''
    const hasLng = longitude.trim() !== ''

    // 前端先擋一次，讓管理員不必等一次往返（後端仍會驗，FR-022）。
    if (hasLat !== hasLng) {
      setLocalError('緯度與經度必須同時填寫，或同時留空。')
      return
    }
    if ((hasLat && Number.isNaN(Number(latitude))) || (hasLng && Number.isNaN(Number(longitude)))) {
      setLocalError('座標必須是數字。')
      return
    }

    onSubmit({
      name: name.trim(),
      address: address.trim(),
      latitude: hasLat ? Number(latitude) : null,
      longitude: hasLng ? Number(longitude) : null,
    })
  }

  const message = localError ?? error

  return (
    <Modal onClose={onCancel} title={store ? '編輯店家' : '新增店家'} variant="center">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={label} htmlFor="store-name">
            店家名稱
          </label>
          <input
            id="store-name"
            className={input}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <p className="mt-1 text-xs text-slate-500">
            允許與其他店家同名（連鎖分店以地址區分）。
          </p>
        </div>

        <div>
          <label className={label} htmlFor="store-address">
            地址
          </label>
          <input
            id="store-address"
            className={input}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={label} htmlFor="store-lat">
              緯度（選填）
            </label>
            <input
              id="store-lat"
              className={input}
              value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
              placeholder="25.0396"
              inputMode="decimal"
            />
          </div>
          <div>
            <label className={label} htmlFor="store-lng">
              經度（選填）
            </label>
            <input
              id="store-lng"
              className={input}
              value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
              placeholder="121.5679"
              inputMode="decimal"
            />
          </div>
        </div>

        {/* FR-026：系統無法驗證地址與座標是否一致，須明白告知管理員。 */}
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <p className="font-medium">關於座標</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            <li>緯度與經度必須同時填寫，或同時留空。</li>
            <li>
              系統<strong>不會</strong>檢查地址與座標是否一致。使用者端的距離計算一律以座標為準，
              地址僅供顯示——座標填錯不會有任何警告。
            </li>
            <li>未填座標的店家不會出現在使用者端的「附近店家」推薦中。</li>
          </ul>
        </div>

        {message && (
          <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">
            {message}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-300 px-4 py-2 text-sm"
          >
            取消
          </button>
          <button
            type="submit"
            disabled={pending}
            className="rounded bg-slate-800 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {pending ? '儲存中…' : '儲存'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
