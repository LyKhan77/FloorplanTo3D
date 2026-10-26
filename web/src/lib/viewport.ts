export interface View {
  scale: number
  x: number
  y: number
}

export const MIN_SCALE = 0.1
export const MAX_SCALE = 20

/** Zoom by `factor` keeping the image point under the cursor (cx, cy in box pixels) in place. */
export function zoomAt(v: View, factor: number, cx: number, cy: number): View {
  const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor))
  const k = scale / v.scale
  return { scale, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }
}

/** Scale and centre an image so it fits inside the box. */
export function fit(imgW: number, imgH: number, boxW: number, boxH: number): View {
  const scale = Math.min(boxW / imgW, boxH / imgH)
  return { scale, x: (boxW - imgW * scale) / 2, y: (boxH - imgH * scale) / 2 }
}
