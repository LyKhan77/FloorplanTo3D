import { Button } from '@carbon/react'
import type { MergeWalls } from '../../types/ops'
import type { Wall } from '../../types/spec'
import { useEditorStore } from '../store'
import { DeleteWithReason } from './DeleteWithReason'

/** Two or more walls selected: merge them, or delete them all in one undo step (their doors go with them). */
export function BulkWalls({ walls }: { walls: Wall[] }) {
  const ids = walls.map((w) => w.id)
  const remove = (reason: string) => {
    const s = useEditorStore.getState()
    const hosted = (s.view?.openings ?? []).filter((o) => ids.includes(o.wall_id))
    const doors = hosted.filter((o) => o.category === 'door').length, windows = hosted.length - doors
    const lost = [doors && `${doors} pintu`, windows && `${windows} jendela`].filter(Boolean).join(' dan ')
    if (s.applyMany(ids.map((id) => ({ op: 'delete_wall' as const, id, reason }))) && lost) {
      s.setNotice({ kind: 'warning', text: `${ids.length} dinding terhapus; ${lost} ikut terhapus` })
    }
  }
  return (
    <>
      <Button size="sm" kind="tertiary"
        onClick={() => useEditorStore.getState().apply({ op: 'merge_walls', ids: ids as MergeWalls['ids'], reason: 'gabung dinding kolinear' })}>
        Gabung
      </Button>
      <DeleteWithReason id="bw-del" label={`Hapus ${ids.length} dinding`} onDelete={remove} />
    </>
  )
}
