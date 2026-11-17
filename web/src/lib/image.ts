/**
 * 上传前在浏览器里压缩照片：长边缩到 1280px、转 JPEG。
 * 手机原图常有 3–8MB，压完一般 150–400KB，上传快、识别也够清楚；顺带按 EXIF 方向摆正。
 */
const MAX_SIDE = 1280
const MAX_DATA_URL = 2_600_000 // 约 1.9MB 图片；服务端上限 3MB，留余量

async function load(file: File): Promise<{ img: CanvasImageSource; w: number; h: number; done: () => void }> {
  if ('createImageBitmap' in window) {
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' })
      return { img: bmp, w: bmp.width, h: bmp.height, done: () => bmp.close() }
    } catch { /* 部分格式不支持，退回 <img> */ }
  }
  const url = URL.createObjectURL(file)
  const img = new Image()
  img.decoding = 'async'
  img.src = url
  await img.decode().catch(() => { URL.revokeObjectURL(url); throw new Error('这张照片打不开，换一张试试') })
  return { img, w: img.naturalWidth, h: img.naturalHeight, done: () => URL.revokeObjectURL(url) }
}

export async function compressImage(file: File): Promise<string> {
  if (!file.type.startsWith('image/')) throw new Error('请选择一张照片')
  const { img, w, h, done } = await load(file)
  try {
    const scale = Math.min(1, MAX_SIDE / Math.max(w, h))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(w * scale))
    canvas.height = Math.max(1, Math.round(h * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('浏览器不支持处理照片')
    ctx.fillStyle = '#fff' // PNG 透明底转 JPEG 会变黑，先铺白
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    for (const q of [0.82, 0.7, 0.55]) {
      const url = canvas.toDataURL('image/jpeg', q)
      if (url.length <= MAX_DATA_URL) return url
    }
    throw new Error('照片太大了，换一张试试')
  } finally { done() }
}
