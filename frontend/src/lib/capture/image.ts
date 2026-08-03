/**
 * 上傳前的前端壓縮與驗證（research.md R-10、FR-019）。
 *
 * 行動網路是主要使用情境，壓縮同時降低上傳時間與辨識服務的解碼負擔。
 */

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024
export const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_EDGE = 1280
const JPEG_QUALITY = 0.85

export type ValidationError = 'unsupported_type' | 'too_large'

/** 送出辨識前先擋掉不合法的檔案（FR-019）。 */
export function validateFile(file: File): ValidationError | null {
  if (!ALLOWED_TYPES.includes(file.type)) return 'unsupported_type'
  if (file.size > MAX_UPLOAD_BYTES) return 'too_large'
  return null
}

export const VALIDATION_MESSAGES: Record<ValidationError, string> = {
  unsupported_type: '不支援這種檔案格式，請選擇 JPEG、PNG 或 WebP 照片。',
  too_large: '照片檔案太大，請選擇 10MB 以內的照片。',
}

/** 縮至最長邊 1280px 並轉為 JPEG。失敗時回原檔，不阻斷流程。 */
export async function compressImage(file: File): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))

    const width = Math.round(bitmap.width * scale)
    const height = Math.round(bitmap.height * scale)

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height

    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.drawImage(bitmap, 0, 0, width, height)
    bitmap.close()

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY)
    )
    return blob ?? file
  } catch {
    // 壓縮是最佳化而非必要步驟——失敗就送原檔。
    return file
  }
}
