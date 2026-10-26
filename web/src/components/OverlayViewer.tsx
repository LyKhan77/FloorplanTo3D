import { Button, Checkbox } from '@carbon/react'
import { Add, FitToScreen, Subtract } from '@carbon/icons-react'
import { useRef, useState } from 'react'
import { fit, zoomAt } from '../lib/viewport'
import type { View } from '../lib/viewport'

export interface OverlayLayer {
  id: string
  label: string
  src: string
  visible: boolean
}

/** Zoom/pan image viewer with stacked transparent layers (used by the M5 stage panels). */
export function OverlayViewer({ src, layers = [], alt }: { src: string; layers?: OverlayLayer[]; alt: string }) {
  const box = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<View>({ scale: 1, x: 0, y: 0 })
  const [visible, setVisible] = useState(() => Object.fromEntries(layers.map((l) => [l.id, l.visible])))
  const drag = useRef<{ x: number; y: number } | null>(null)

  const center = () => {
    const r = box.current?.getBoundingClientRect()
    return r ? [r.width / 2, r.height / 2] : [0, 0]
  }
  const reset = (img?: HTMLImageElement) => {
    const r = box.current?.getBoundingClientRect()
    const i = img ?? box.current?.querySelector('img')
    if (r && i) setView(fit(i.naturalWidth, i.naturalHeight, r.width, r.height))
  }

  return (
    <div className="overlay-viewer">
      <div className="overlay-toolbar">
        <Button kind="ghost" size="sm" hasIconOnly renderIcon={Add} iconDescription="Perbesar" onClick={() => setView((v) => zoomAt(v, 1.25, ...center() as [number, number]))} />
        <Button kind="ghost" size="sm" hasIconOnly renderIcon={Subtract} iconDescription="Perkecil" onClick={() => setView((v) => zoomAt(v, 0.8, ...center() as [number, number]))} />
        <Button kind="ghost" size="sm" hasIconOnly renderIcon={FitToScreen} iconDescription="Pas layar" onClick={() => reset()} />
        {layers.map((l) => (
          <Checkbox key={l.id} id={`layer-${l.id}`} labelText={l.label} checked={visible[l.id]}
            onChange={(_e, { checked }) => setVisible((s) => ({ ...s, [l.id]: checked }))} />
        ))}
      </div>
      <div ref={box} className="overlay-box"
        onWheel={(e) => {
          const r = box.current!.getBoundingClientRect()
          setView((v) => zoomAt(v, e.deltaY < 0 ? 1.1 : 1 / 1.1, e.clientX - r.left, e.clientY - r.top))
        }}
        onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY }; (e.target as Element).setPointerCapture?.(e.pointerId) }}
        onPointerMove={(e) => {
          if (!drag.current) return
          const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y
          drag.current = { x: e.clientX, y: e.clientY }
          setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }))
        }}
        onPointerUp={() => { drag.current = null }}>
        <div className="overlay-stage" style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}>
          <img src={src} alt={alt} draggable={false} onLoad={(e) => reset(e.currentTarget)} />
          {layers.filter((l) => visible[l.id]).map((l) => <img key={l.id} src={l.src} alt="" aria-hidden="true" draggable={false} className="overlay-layer" />)}
        </div>
      </div>
    </div>
  )
}
