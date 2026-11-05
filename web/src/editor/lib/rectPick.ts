import type { Room, Spec } from '../../types/spec'

export type ScreenRect = { xa: number; xb: number; ya: number; yb: number }

/** Ids a marquee box selects: walls with both ends inside, then objects whose position is inside; a hidden layer is
 * skipped, so hiding objects gives a walls-only box. */
export function idsInRect(view: Spec, rect: ScreenRect, toScreen: (p: [number, number, number]) => [number, number],
  layers: { walls: boolean; objects: boolean } = { walls: true, objects: true }): string[] {
  const inside = (p: [number, number, number]) => {
    const [x, y] = toScreen(p)
    return x >= rect.xa && x <= rect.xb && y >= rect.ya && y <= rect.yb
  }
  const walls = (layers.walls ? view.walls ?? [] : []).filter((w) => inside([w.a[0], w.a[1], 0]) && inside([w.b[0], w.b[1], 0]))
  const objects = (layers.objects ? view.objects ?? [] : []).filter((o) => inside(o.position as [number, number, number]))
  return [...walls, ...objects].map((e) => e.id)
}

/** Rooms a marquee holds whole. A wall box cuts the rooms around it, so it takes none of those. */
export function roomsInRect(rooms: Room[], rect: ScreenRect, toScreen: (p: [number, number, number]) => [number, number]): string[] {
  const inside = (p: number[]) => {
    const [x, y] = toScreen([p[0], p[1], 0])
    return x >= rect.xa && x <= rect.xb && y >= rect.ya && y <= rect.yb
  }
  return rooms.filter((r) => r.polygon.every(inside)).map((r) => r.id)
}
