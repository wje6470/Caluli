'use client'

/**
 * 破壞性操作的二次確認（FR-038、FR-039）。
 *
 * 刪除為實刪除且無法還原，連帶刪除的餐點也一併消失，故這個對話框是唯一的
 * 防誤刪機制——訊息必須明確告知「將一併刪除幾道餐點」，而不是只問
 * 「確定嗎？」。
 */

import { Modal } from '@/components/ui/Modal'

type Props = {
  title: string
  message: string
  /** 額外強調的後果，例如連帶刪除的餐點數。 */
  consequence?: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
  pending: boolean
}

export function ConfirmDialog({
  title,
  message,
  consequence,
  confirmLabel,
  onConfirm,
  onCancel,
  pending,
}: Props) {
  return (
    <Modal onClose={onCancel} title={title} variant="center">
      <div className="space-y-3">
        <p className="text-sm text-slate-700">{message}</p>

        {consequence && (
          <p className="rounded border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800">
            {consequence}
          </p>
        )}

        <p className="text-xs text-slate-500">此操作無法復原。</p>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-300 px-4 py-2 text-sm"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className="rounded bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {pending ? '刪除中…' : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  )
}
