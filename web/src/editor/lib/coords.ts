/** Spec mm (+X east, +Y north, +Z up) <-> three meters (Y up): X = x/1000, Y = z/1000, Z = -y/1000. */
export function toThree(p: [number, number, number?] | number[]): [number, number, number] {
  return [p[0] / 1000, (p[2] ?? 0) / 1000, -p[1] / 1000 + 0]
}

export function fromThree(v: { x: number; y: number; z: number }): [number, number, number] {
  return [v.x * 1000 + 0, -v.z * 1000 + 0, v.y * 1000 + 0]
}

/** Spec rotation is degrees CCW about +Z; in three that is a positive rotation about +Y. */
export const rotToThree = (deg: number): number => (deg * Math.PI) / 180
