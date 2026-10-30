/** Viewer layers of the installation GLB, from the exported object names (core/installation/geometry.py, build.py). */
export const LAYERS = ['Tray data', 'Tray power', 'Hanger', 'Drop', 'Rack', 'Plafon', 'Raised floor'] as const
export type Layer = (typeof LAYERS)[number]
export const LAYERS_OFF: Layer[] = ['Plafon']  // the ceiling hides the room from above until switched on

const PREFIX: [string, Layer][] = [['tray_data_', 'Tray data'], ['tray_power_', 'Tray power'], ['hanger_', 'Hanger'],
  ['drop_', 'Drop'], ['rack_', 'Rack'], ['ceiling', 'Plafon'], ['raised_floor', 'Raised floor']]

export function layerOf(name: string): Layer | null {
  return PREFIX.find(([p]) => name.startsWith(p))?.[1] ?? null
}
