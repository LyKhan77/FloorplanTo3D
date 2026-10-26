import { Euler, Matrix4, Quaternion, Vector3 } from 'three'
import type { Template } from '../../api/types'
import { rotToThree, toThree } from '../lib/coords'
import { templateOf } from '../lib/transform'
import { useEditorStore } from '../store'
import { unitBox } from './objectMatrix'

const SLAB = 30 // mm

/** Service clearance in front (+Y local) and behind each selected object, from template.clearance. */
export function Clearance({ templates }: { templates: Template[] }) {
  const view = useEditorStore((s) => s.view)
  const selection = useEditorStore((s) => s.selection)
  const boxes = (view?.objects ?? []).filter((o) => selection.includes(o.id)).flatMap((o) => {
    const c = templateOf(o, templates)?.clearance ?? {}
    const [w, d] = o.dims
    const rot = new Quaternion().setFromEuler(new Euler(0, rotToThree(o.rotation ?? 0), 0))
    return ([['front', c.front ?? 0, 1], ['back', c.back ?? 0, -1]] as const).filter(([, depth]) => depth > 0).map(([side, depth, dir]) => {
      // local offset along spec +Y (three -Z), rotated with the object
      const offset = new Vector3(0, 0, -dir * (d / 2 + depth / 2) / 1000).applyQuaternion(rot)
      const m = new Matrix4().compose(new Vector3(...toThree(o.position)).add(offset), rot, new Vector3(w / 1000, SLAB / 1000, depth / 1000))
      return { key: `${o.id}-${side}`, m }
    })
  })
  return (
    <>
      {boxes.map(({ key, m }) => (
        <mesh key={key} geometry={unitBox} matrix={m} matrixAutoUpdate={false} raycast={() => null}>
          <meshBasicMaterial color="#42be65" transparent opacity={0.3} depthWrite={false} />
        </mesh>
      ))}
    </>
  )
}
