import { CodeSnippet, Dropdown, Modal, Tile } from '@carbon/react'
import { useState } from 'react'
import { useTemplates } from '../api/hooks'
import type { Template } from '../api/types'

export function TemplatesPage() {
  const { data: templates = [], isLoading } = useTemplates()
  const [category, setCategory] = useState<string>('semua')
  const [open, setOpen] = useState<Template | null>(null)
  const categories = ['semua', ...Array.from(new Set(templates.map((t) => t.category))).sort()]
  const shown = templates.filter((t) => category === 'semua' || t.category === category)
  return (
    <>
      <h1 className="page-title">Templates</h1>
      <div className="narrow-filter">
        <Dropdown id="tpl-cat" titleText="Kategori" label="Kategori" items={categories} selectedItem={category}
          onChange={({ selectedItem }) => setCategory(selectedItem ?? 'semua')} />
      </div>
      {!isLoading && !shown.length && <p className="helper">Belum ada template. Jalankan core.templates.make_placeholders atau tambahkan paket ke folder templates/.</p>}
      <div className="template-grid">
        {shown.map((t) => (
          <Tile key={`${t.id}@${t.version}`} className="template-card">
            <button type="button" className="template-open" onClick={() => setOpen(t)} aria-label={`Detail ${t.name}`}>
              <img src={t.thumbnail_url} alt="" loading="lazy" />
            </button>
            <strong>{t.name}</strong>
            <span className="helper">{t.category} · v{t.version}</span>
            <span className="mono helper">{t.dims.w} × {t.dims.d} × {t.dims.h} mm</span>
          </Tile>
        ))}
      </div>
      <Modal open={open !== null} passiveModal modalHeading={open?.name ?? ''} onRequestClose={() => setOpen(null)}>
        <p className="helper">Pratinjau 3D tersedia di M4.</p>
        {open && <CodeSnippet type="multi" feedback="Disalin">{JSON.stringify(open, null, 2)}</CodeSnippet>}
      </Modal>
    </>
  )
}
