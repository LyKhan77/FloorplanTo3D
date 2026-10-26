import { useRegenerate } from '../api/hooks'
import type { Run } from '../api/types'
import { useEditorStore } from './store'

const BLENDER = [7, 8, 9, 10]

/** Regenerate the saved base version and follow stages 7–10 of the active run (0–100 %). */
export function useRegenerateFlow(projectId: string, run: Run | null) {
  const mutation = useRegenerate(projectId)
  const running = !!run && (run.status === 'queued' || run.status === 'running')
  const stages = running ? run!.stages.filter((s) => BLENDER.includes(s.n)) : []
  const current = stages.find((s) => s.status === 'running')
  const done = stages.filter((s) => s.status === 'succeeded' || s.status === 'skipped').length
  return {
    regenerate: (version?: number) => {
      const v = version ?? useEditorStore.getState().baseVersion
      if (v !== null) mutation.mutate(v, { onError: (e) => useEditorStore.getState().setNotice({ kind: 'error', text: e.message }) })
    },
    running: running || mutation.isPending,
    progress: running ? ((done + (current?.progress ?? 0)) / BLENDER.length) * 100 : null,
    stage: current?.name ?? null,
  }
}
