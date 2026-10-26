import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { Spec } from '../types/spec'
import type { AppConfig, Health, OutputVersion, Profile, ProjectDetail, ProjectSummary, Run, SpecDiff, SpecVersion, Template } from './types'

const P = (id: string) => `/api/projects/${id}`

export const useProjects = () =>
  useQuery({ queryKey: ['projects'], queryFn: () => api.get<{ items: ProjectSummary[]; total: number }>('/api/projects'), refetchInterval: 5000 })
export const useProject = (id: string) => useQuery({ queryKey: ['project', id], queryFn: () => api.get<ProjectDetail>(P(id)) })
export const useRuns = (id: string) => useQuery({ queryKey: ['runs', id], queryFn: () => api.get<Run[]>(`${P(id)}/runs`) })
export const useSpecs = (id: string) => useQuery({ queryKey: ['specs', id], queryFn: () => api.get<SpecVersion[]>(`${P(id)}/specs`) })
export const useSpecDiff = (id: string, from: number | null, to: number | null) =>
  useQuery({
    queryKey: ['diff', id, from, to],
    queryFn: () => api.get<SpecDiff>(`${P(id)}/specs/diff?from=${from}&to=${to}`),
    enabled: from !== null && to !== null && from !== to,
  })
export const useSpecHead = (id: string) => useQuery({ queryKey: ['spec', id, 'HEAD'], queryFn: () => api.get<Spec>(`${P(id)}/specs/HEAD`) })
export const useOutputs = (id: string) => useQuery({ queryKey: ['outputs', id], queryFn: () => api.get<OutputVersion[]>(`${P(id)}/outputs`) })
export const useTemplates = () => useQuery({ queryKey: ['templates'], queryFn: () => api.get<Template[]>('/api/templates') })
export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: () => api.get<Health>('/api/health'), refetchInterval: 10000 })
export const useProfiles = () => useQuery({ queryKey: ['profiles'], queryFn: () => api.get<Profile[]>('/api/profiles') })
export const useConfig = () => useQuery({ queryKey: ['config'], queryFn: () => api.get<AppConfig>('/api/config') })

function useInvalidate(id?: string) {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['projects'] })
    if (id) for (const k of ['project', 'runs', 'specs', 'outputs', 'spec']) qc.invalidateQueries({ queryKey: [k, id] })
  }
}

export function useCreateProject() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (form: FormData) => api.upload<{ project_id: string; run_id: string | null }>('/api/projects', form),
    onSuccess: invalidate,
  })
}

export function useImportSpec(id: string) {
  const invalidate = useInvalidate(id)
  return useMutation({ mutationFn: (json: string) => api.postRaw<{ version: number }>(`${P(id)}/specs/import`, json, 'application/json'), onSuccess: invalidate })
}

export function useStartRun(id: string) {
  const invalidate = useInvalidate(id)
  return useMutation({
    mutationFn: (body: { kind: string; from_stage?: number; params_override?: Record<string, unknown>; profile_id?: string }) =>
      api.post<{ run_id: string }>(`${P(id)}/runs`, body),
    onSuccess: invalidate,
  })
}

export function useRegenerate(id: string) {
  const invalidate = useInvalidate(id)
  return useMutation({
    mutationFn: (version: number | 'HEAD') => api.post<{ run_id: string | null; reused?: boolean }>(`${P(id)}/regenerate`, { version }),
    onSuccess: invalidate,
  })
}

export function useCancelRun(id: string) {
  const invalidate = useInvalidate(id)
  return useMutation({ mutationFn: (runId: string) => api.post(`${P(id)}/runs/${runId}/cancel`), onSuccess: invalidate })
}

export function useDeleteProject() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: (id: string) => api.del(`${P(id)}?confirm=true`), onSuccess: invalidate })
}

export function useSaveProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; from_run: string }) => api.post<Profile>('/api/profiles', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles'] }),
  })
}

export function useContinueRun(id: string) {
  const invalidate = useInvalidate(id)
  return useMutation({
    mutationFn: (runId: string) => api.post<{ run_id: string }>(`${P(id)}/runs/${runId}/continue`, { accept_low_score: true }),
    onSuccess: invalidate,
  })
}
