export interface ProjectFields {
  name?: string
  prompt?: string
  wallHeight?: number | null
  doorHeight?: number | null
  wallThickness?: number | null
  floorName?: string
  siteType?: string
  mmPerPx?: number | null
  useStrata?: boolean
  profileId?: string | null
  start: boolean
}

/** multipart body for POST /api/projects; only filled advanced parameters are sent (FR-IN-03). */
export function buildProjectForm(file: File, f: ProjectFields): FormData {
  const params: Record<string, unknown> = {}
  const num = (key: string, v: number | null | undefined) => {
    if (v === null || v === undefined || Number.isNaN(v)) return
    if (v <= 0) throw new Error(`${key} must be greater than 0`)
    params[key] = v
  }
  num('wall_height', f.wallHeight)
  num('door_height', f.doorHeight)
  num('wall_thickness', f.wallThickness)
  if (f.floorName) params.floor_name = f.floorName
  if (f.siteType) params.site_type = f.siteType
  num('mm_per_px', f.mmPerPx)
  if (f.useStrata !== undefined) params.use_strata = f.useStrata

  const fd = new FormData()
  fd.append('file', file)
  fd.append('name', f.name || file.name.replace(/\.[^.]+$/, ''))
  if (f.prompt) fd.append('prompt', f.prompt)
  if (Object.keys(params).length) fd.append('params', JSON.stringify(params))
  if (f.profileId) fd.append('profile_id', f.profileId)
  fd.append('start', String(f.start))
  return fd
}
