import { BoxGeometry, EdgesGeometry, Euler, Matrix4, Quaternion, Vector3 } from 'three'
import type { Template } from '../../api/types'
import type { PlacedObject } from '../../types/spec'
import { rotToThree, toThree } from '../lib/coords'
import { scaleOf } from '../lib/resize'

/** Unit cube with its pivot at the bottom centre, like template assets. */
export const unitBox = new BoxGeometry(1, 1, 1).translate(0, 0.5, 0)
export const boxEdges = new EdgesGeometry(unitBox)

export function objectMatrix(o: Pick<PlacedObject, 'position' | 'rotation' | 'dims'>, t: Template | undefined): Matrix4 {
  const dims = o.dims as [number, number, number]
  const s = t ? scaleOf(dims, t) : [dims[0] / 1000, dims[2] / 1000, dims[1] / 1000]
  return new Matrix4().compose(new Vector3(...toThree(o.position)),
    new Quaternion().setFromEuler(new Euler(0, rotToThree(o.rotation ?? 0), 0)), new Vector3(...s))
}

export const shouldInstance = (count: number): boolean => count > 20
