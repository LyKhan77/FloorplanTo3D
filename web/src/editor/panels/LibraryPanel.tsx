import { Dropdown, Search } from '@carbon/react'
import { useState } from 'react'
import type { Template } from '../../api/types'
import { useEditorStore } from '../store'

/** Template categories (PRD/10 §2). */
const CATEGORIES = ['semua', 'rack', 'cooling', 'power', 'battery', 'network', 'fire', 'security', 'furniture', 'structure', 'other']

export function LibraryPanel({ templates }: { templates: Template[] }) {
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('semua')
  const needle = q.trim().toLowerCase()
  const shown = templates.filter((t) => (category === 'semua' || t.category === category)
    && (!needle || [t.name, t.id, ...(t.tags ?? [])].some((s) => s.toLowerCase().includes(needle))))
  return (
    <section className="editor-panel" aria-label="Library">
      <h4 className="editor-panel__title">Library</h4>
      <Search size="sm" labelText="Cari template" placeholder="Cari template" value={q} onChange={(e) => setQ(e.target.value)} />
      <Dropdown id="lib-cat" titleText="Kategori" label="Kategori" size="sm" items={CATEGORIES} selectedItem={category}
        onChange={({ selectedItem }) => setCategory(selectedItem ?? 'semua')} />
      <ul className="editor-library">
        {shown.map((t) => (
          <li key={`${t.id}@${t.version}`} draggable className="editor-library__card" title="Seret ke lantai ruang"
            onDragStart={(e) => {
              e.dataTransfer.setData('application/x-template', `${t.id}@${t.version}`)
              e.dataTransfer.effectAllowed = 'copy'
              useEditorStore.getState().setDragging(t)
            }}
            onDragEnd={() => useEditorStore.getState().setDragging(null)}>
            <img src={t.thumbnail_url} alt="" loading="lazy" draggable={false} />
            <span>
              <strong>{t.name}</strong>
              <span className="mono helper">{t.dims.w} × {t.dims.d} × {t.dims.h}</span>
            </span>
          </li>
        ))}
      </ul>
      {!shown.length && <p className="helper">Tidak ada template yang cocok.</p>}
    </section>
  )
}
