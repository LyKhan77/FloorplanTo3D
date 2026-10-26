import { outputsBase } from '../api/client'
import { useOutputs, useSpecHead, useTemplates } from '../api/hooks'
import type { Template } from '../api/types'
import type { Spec } from '../types/spec'

export interface EditorData {
  spec?: Spec
  shellVersion: number | null
  shellUrl: string | null
  stale: boolean
  templates: Template[]
  loading: boolean
}

/** HEAD spec plus the newest published shell.glb at or below HEAD (a shell from an older version is "stale"). */
export function useEditorData(projectId: string): EditorData {
  const spec = useSpecHead(projectId)
  const outputs = useOutputs(projectId)
  const templates = useTemplates()
  const head = spec.data?.meta.version ?? null
  const shellVersion = (outputs.data ?? [])
    .filter((o) => (head === null || o.version <= head) && o.files.some((f) => f.name === 'shell.glb'))
    .reduce<number | null>((best, o) => (best === null || o.version > best ? o.version : best), null)
  return {
    spec: spec.data,
    shellVersion,
    shellUrl: shellVersion === null ? null : `${outputsBase(projectId, shellVersion)}/shell.glb`,
    stale: shellVersion !== null && shellVersion !== head,
    templates: templates.data ?? [],
    loading: spec.isLoading || outputs.isLoading,
  }
}
