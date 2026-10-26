import { formatM, formatM2 } from './lib/measure'
import { useEditorStore } from './store'

export function StatusBar() {
  const { cursor, hoverRoom, fps, view } = useEditorStore()
  const room = view?.rooms?.find((r) => r.id === hoverRoom)
  return (
    <div className="editor__status mono" aria-live="off">
      <span>kursor {cursor ? `X ${formatM(cursor[0])}  Y ${formatM(cursor[1])}` : '—'}</span>
      <span>Ruang: {room ? `${room.name || room.id} ${room.area_m2 != null ? formatM2(room.area_m2) : ''}` : '—'}</span>
      <span>{fps === null ? '—' : `${Math.round(fps)} fps`}</span>
    </div>
  )
}
