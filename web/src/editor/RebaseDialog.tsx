import { Modal } from '@carbon/react'
import type { Spec } from '../types/spec'
import { targetIds } from './ops/compose'
import type { OpFailure } from './ops/reducer'
import { useEditorStore } from './store'

/** Another tab saved first: replay the local ops on HEAD, dropping the ones that no longer apply. */
export function RebaseDialog({ conflict, onResolve }: { conflict: { head: Spec; failed: OpFailure[] } | null; onResolve(accept: boolean): void }) {
  const ops = useEditorStore((s) => s.ops)
  const head = conflict?.head.meta.version
  return (
    <Modal open={!!conflict} modalHeading={`Spec sudah berubah (HEAD v${head})`} primaryButtonText={`Terapkan ke v${head}`}
      secondaryButtonText="Batal" onRequestSubmit={() => onResolve(true)} onRequestClose={() => onResolve(false)}>
      <p>Tab atau pengguna lain menyimpan versi baru. Ops lokal Anda akan diterapkan ulang di atas v{head}.</p>
      {conflict && conflict.failed.length > 0 ? (
        <>
          <p className="helper">Op berikut tidak bisa diterapkan dan akan dibuang:</p>
          <ul className="editor-rebase">
            {conflict.failed.map((f) => (
              <li key={f.index} className="mono">#{f.index + 1} {f.op} {ops[f.index] ? targetIds(ops[f.index]).join(', ') : ''}: {f.message}</li>
            ))}
          </ul>
        </>
      ) : <p className="helper">Semua op bisa diterapkan.</p>}
    </Modal>
  )
}
