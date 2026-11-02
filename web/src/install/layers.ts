import { Plane, Vector3 } from 'three'

/** Viewer layers of the installation GLB, from the exported object names (core/installation/geometry.py, build.py). */
export const LAYERS = ['Tray data', 'Tray power', 'Hanger', 'Drop', 'Rack', 'Dinding', 'Plafon', 'Raised floor'] as const
export type Layer = (typeof LAYERS)[number]
export const LAYERS_OFF: Layer[] = ['Plafon']  // the ceiling hides the room from above until switched on

/** the building parts that stand between an outside view and the trays: cut away like the iso renders */
const BUILDING = ['wall_', 'column_', 'door_', 'frame_', 'leaf_', 'window_']

const PREFIX: [string, Layer][] = [['tray_data_', 'Tray data'], ['tray_power_', 'Tray power'], ['hanger_', 'Hanger'],
  ['drop_', 'Drop'], ['rack_', 'Rack'], ['ceiling', 'Plafon'], ['raised_floor', 'Raised floor'],
  ...BUILDING.map((p): [string, Layer] => [p, 'Dinding'])]

export function layerOf(name: string): Layer | null {
  return PREFIX.find(([p]) => name.startsWith(p))?.[1] ?? null
}

export const CUT_M = 1.2  // as the layout's iso renders (cutaway 1200 mm)

/** Clipping planes for the building parts: keep what is below CUT_M (three.js is y-up, metres). */
export function cutaway(on: boolean): Plane[] {
  return on ? [new Plane(new Vector3(0, -1, 0), CUT_M)] : []
}

