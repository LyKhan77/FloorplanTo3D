import { ErrorFilled, InformationFilled, WarningAltFilled } from '@carbon/icons-react'
import { Button, Tag } from '@carbon/react'
import { useMemo } from 'react'
import { collisionsOf } from '../lib/obb'
import { useEditorStore, type Issue } from '../store'

const ICON = { error: ErrorFilled, warning: WarningAltFilled, info: InformationFilled }
const key = (i: Issue) => `${i.code}|${i.element_ids.join(',')}`

/** Validation issues + Save issues + collisions (V017, warning only) + missing templates; element ids select. */
export function IssuesPanel({ issues, newIssues, extra = [] }: { issues: Issue[]; newIssues: Set<string>; extra?: Issue[] }) {
  const saveIssues = useEditorStore((s) => s.saveIssues)
  const missing = useEditorStore((s) => s.missingTemplates)
  const select = useEditorStore((s) => s.select)
  const view = useEditorStore((s) => s.view)
  const clashes = useMemo<Issue[]>(() => (view ? collisionsOf(view) : []).map(({ a, b }) => ({
    code: 'V017', severity: 'warning', element_ids: [a, b], message: `Tabrakan ${a} ↔ ${b}` })), [view])
  const all: Issue[] = [
    ...saveIssues, ...issues.filter((i) => !saveIssues.some((s) => key(s) === key(i))), ...extra,
    ...clashes.filter((c) => !issues.some((i) => key(i) === key(c))),
    ...(missing.length ? [{ code: 'TEMPLATE', severity: 'warning' as const, element_ids: missing,
      message: 'Template tidak ada di registry; objek ditampilkan sebagai kotak abu-abu' }] : []),
  ]
  return (
    <section className="editor-panel" aria-label="Masalah">
      <h4 className="editor-panel__title">Masalah ({all.length})</h4>
      {!all.length && <p className="helper">Tidak ada masalah.</p>}
      <ul className="editor-issues">
        {all.map((i, n) => {
          const Icon = ICON[i.severity]
          return (
            <li key={`${key(i)}#${n}`} className={`editor-issue editor-issue--${i.severity}`}>
              <Icon aria-label={i.severity} />
              <div>
                <span className="mono">{i.code}</span>
                {newIssues.has(key(i)) && <Tag size="sm" type="magenta">baru</Tag>}
                <p>{i.message}</p>
                <span className="editor-issue__ids">
                  {i.element_ids.map((id) => <Button key={id} kind="ghost" size="sm" onClick={() => select([id])}>{id}</Button>)}
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
