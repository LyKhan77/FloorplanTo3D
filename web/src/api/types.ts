// Response shapes of the server (PRD/09). Spec types are generated in ../types/spec.ts.

export type StageStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped' | 'needs_attention' | 'queued'
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'needs_attention' | 'failed'
export type RunKind = 'full' | 'from_stage' | 'regenerate'

export interface Stage {
  n: number
  name: string
  status: StageStatus
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  progress: number | null
  metrics: Record<string, unknown>
  warnings: string[]
}

export interface Run {
  run_id: string
  project_id: string
  kind: RunKind
  from_stage: number
  version: number | null
  spec_version_in: number | null
  spec_version_out: number | null
  status: RunStatus
  stages: Stage[]
  code_version: string
  blender_version: string | null
  created_at: string
  error: string | null
}

export interface ApiEvent {
  seq: number
  ts: string
  run_id: string | null
  stage: number | null
  type: string
  level: 'debug' | 'info' | 'warn' | 'error' | string
  msg: string
  data: Record<string, unknown>
}

export interface ProjectSummary {
  project_id: string
  name: string
  floor: string | null
  status: RunStatus | 'new'
  active_stage: number | null
  validator_score: number | null
  iou: number | null
  head_version: number | null
  updated_at: string
}

export interface ProjectDetail {
  project_id: string
  name: string
  created_at: string
  updated_at: string
  params: Record<string, unknown>
  status: string
  latest_run: Run | null
  head: number | null
  outputs: number[]
  summary: ProjectSummary
}

export interface SpecVersion {
  version: number
  source: string
  created_at: string
  message: string
  run_id: string | null
  has_outputs: boolean
}

export interface DiffEntry {
  added: string[]
  removed: string[]
  changed: string[]
}
export type SpecDiff = Record<string, DiffEntry> & { ops?: { op: string; id?: string | null; by?: string | null; reason?: string | null }[] }

export interface OutputVersion {
  version: number
  files: { name: string; bytes: number }[]
  renders: string[]
}

export interface Template {
  id: string
  version: string
  name: string
  category: string
  dims: { w: number; d: number; h: number }
  thumbnail_url: string
  asset_url: string
  [key: string]: unknown
}

export interface Health {
  server: string
  strata: { ok: boolean; status: string | null; latency_ms: number | null }
  blender: { ok: boolean; version: string | null; busy: boolean }
  queue: { waiting: number; running: string[] }
}

export interface AppConfig {
  llm_tasks_enabled: string[]
  schema_version: string
  code_version: string
  strata_base_url: string
  strata_model: string
  blender_bin: string
  max_upload_mb: number
  [key: string]: unknown
}
