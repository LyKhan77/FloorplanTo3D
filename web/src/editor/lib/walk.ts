const WALK = 1400, RUN = 3000 // mm/s

/**
 * One walk-mode step in plan mm. yaw is the three camera's rotation.y: 0 looks north (+Y spec), positive turns left.
 * input.f / input.r in [-1, 1]; the step is cancelled when blocked(from, to).
 */
export function walkStep(pos: [number, number], yawRad: number, input: { f: number; r: number }, dtS: number, run: boolean,
  blocked: (from: [number, number], to: [number, number]) => boolean): [number, number] {
  const len = Math.hypot(input.f, input.r)
  if (!len) return pos
  const s = ((run ? RUN : WALK) * dtS) / Math.max(1, len)
  const fx = -Math.sin(yawRad), fy = Math.cos(yawRad) // forward
  const rx = Math.cos(yawRad), ry = Math.sin(yawRad) // right
  const to: [number, number] = [pos[0] + (fx * input.f + rx * input.r) * s, pos[1] + (fy * input.f + ry * input.r) * s]
  return blocked(pos, to) ? pos : to
}
