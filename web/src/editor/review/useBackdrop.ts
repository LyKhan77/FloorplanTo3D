import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { Backdrop } from '../../api/types'

/** The page image under the review canvas (GET /backdrop); null while loading or when no run has one. */
export function useBackdrop(projectId: string): Backdrop | null {
  const [b, setB] = useState<Backdrop | null>(null)
  useEffect(() => {
    let live = true
    api.get<Backdrop>(`/api/projects/${projectId}/backdrop`).then((r) => { if (live) setB(r) }).catch(() => { if (live) setB(null) })
    return () => { live = false }
  }, [projectId])
  return b
}
