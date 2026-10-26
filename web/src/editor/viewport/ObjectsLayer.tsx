import { useGLTF } from '@react-three/drei'
import type { ThreeEvent } from '@react-three/fiber'
import { Suspense, useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import { EdgesGeometry, InstancedMesh, Matrix4, Mesh, type Object3D } from 'three'
import type { Template } from '../../api/types'
import type { PlacedObject } from '../../types/spec'
import { useEditorStore } from '../store'
import { objectMatrix, shouldInstance, unitBox } from './objectMatrix'

const boxEdges = new EdgesGeometry(unitBox)

function pick(e: ThreeEvent<MouseEvent>, id: string | undefined) {
  const s = useEditorStore.getState()
  if (!id || s.tool !== 'select' || s.mode === 'walk') return
  e.stopPropagation()
  s.select([id], e.shiftKey)
}

function Instanced({ t, objs, scene }: { t: Template; objs: PlacedObject[]; scene: Object3D }) {
  const meshes = useMemo(() => {
    scene.updateMatrixWorld(true)
    const out: Mesh[] = []
    scene.traverse((o) => { if (o instanceof Mesh) out.push(o) })
    return out
  }, [scene])
  return <>{meshes.map((m) => <InstancedPart key={m.uuid} mesh={m} t={t} objs={objs} />)}</>
}

function InstancedPart({ mesh, t, objs }: { mesh: Mesh; t: Template; objs: PlacedObject[] }) {
  const ref = useRef<InstancedMesh>(null)
  useLayoutEffect(() => {
    const im = ref.current
    if (!im) return
    const m = new Matrix4()
    objs.forEach((o, i) => im.setMatrixAt(i, m.multiplyMatrices(objectMatrix(o, t), mesh.matrixWorld)))
    im.instanceMatrix.needsUpdate = true
    im.computeBoundingSphere()
    if (import.meta.env.DEV) {
      const w = window as unknown as { __editorStats?: { instanced?: Record<string, number> } }
      w.__editorStats = { ...w.__editorStats, instanced: { ...w.__editorStats?.instanced, [t.id]: objs.length } }
    }
  }, [objs, t, mesh])
  return (
    <instancedMesh key={objs.length} ref={ref} args={[mesh.geometry, mesh.material, objs.length]}
      onClick={(e) => pick(e, e.instanceId === undefined ? undefined : objs[e.instanceId]?.id)} />
  )
}

function Cloned({ o, t, scene }: { o: PlacedObject; t: Template; scene: Object3D }) {
  const obj = useMemo(() => scene.clone(), [scene])
  const matrix = useMemo(() => objectMatrix(o, t), [o, t])
  return <primitive object={obj} matrix={matrix} matrixAutoUpdate={false} onClick={(e: ThreeEvent<MouseEvent>) => pick(e, o.id)} />
}

function TemplateGroup({ t, objs }: { t: Template; objs: PlacedObject[] }) {
  const { scene } = useGLTF(t.asset_url)
  if (shouldInstance(objs.length)) return <Instanced t={t} objs={objs} scene={scene} />
  return <>{objs.map((o) => <Cloned key={o.id} o={o} t={t} scene={scene} />)}</>
}

/** Template objects of the view; groups over 20 instances use InstancedMesh, missing templates a grey box. */
export function ObjectsLayer({ templates }: { templates: Template[] }) {
  const objects = useEditorStore((s) => s.view?.objects)
  const visible = useEditorStore((s) => s.layers.objects)
  const selection = useEditorStore((s) => s.selection)
  const registry = useMemo(() => new Map(templates.map((t) => [`${t.id}@${t.version}`, t])), [templates])
  const groups = useMemo(() => {
    const g = new Map<string, PlacedObject[]>()
    for (const o of objects ?? []) {
      const k = `${o.template_id}@${o.template_version}`
      g.set(k, [...(g.get(k) ?? []), o])
    }
    return [...g]
  }, [objects])
  const missing = groups.filter(([k]) => !registry.has(k))
  const missingKey = missing.flatMap(([, objs]) => objs.map((o) => o.id)).join(',')

  useEffect(() => {
    useEditorStore.getState().setMissingTemplates(missingKey ? missingKey.split(',') : [])
  }, [missingKey])

  const selected = (objects ?? []).filter((o) => selection.includes(o.id))
  return (
    <group visible={visible}>
      {groups.map(([k, objs]) => registry.has(k) && (
        <Suspense key={k} fallback={null}><TemplateGroup t={registry.get(k)!} objs={objs} /></Suspense>
      ))}
      {missing.flatMap(([, objs]) => objs).map((o) => (
        <mesh key={o.id} geometry={unitBox} matrix={objectMatrix(o, undefined)} matrixAutoUpdate={false} onClick={(e) => pick(e, o.id)}>
          <meshStandardMaterial color="#8d8d8d" />
        </mesh>
      ))}
      {selected.map((o) => (
        <lineSegments key={o.id} geometry={boxEdges} matrix={objectMatrix(o, undefined)} matrixAutoUpdate={false} renderOrder={10}>
          <lineBasicMaterial color="#0f62fe" depthTest={false} transparent />
        </lineSegments>
      ))}
    </group>
  )
}
