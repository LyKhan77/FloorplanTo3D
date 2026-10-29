/** The review canvas draws in mm with y flipped (SVG y runs down, spec y runs up). */
export const svgPoint = ([x, y]: [number, number] | number[]): [number, number] => [x, -y]

/** SVG transform that lays a page image (px) under the plan: spec px -> mm is x = a·px + b·py + c, y = d·px + e·py + f. */
export function imageMatrix(pxToMm: number[]): string {
  const [a, b, c, d, e, f] = pxToMm
  return `matrix(${a},${-d},${b},${-e},${c},${-f})`
}
